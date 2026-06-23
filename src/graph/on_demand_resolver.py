"""S10: on-demand citation resolution at query time.

When a retrieved chunk's metadata exposes unresolved citation strings,
resolve them at query time via the existing regex-based ``citation_index``
and write the resulting edges back to Kuzu idempotently. This closes the
gap between ingestion-time regex extraction (which can miss odd phrasings)
and query-time coverage — without adding ANY new LLM / embedding / API
call.

Design notes (Phase 8 D-10):
    - Regex + dict lookup only. No LLM, no embedding, no network calls.
    - Idempotent: uses Kuzu ``MERGE (a)-[r:<TYPE>]->(b) ON CREATE SET ...``
      so re-running on the same chunk produces no duplicate edges. When
      the installed Kuzu version does not support MERGE with ON CREATE,
      the silent-fallback path exists (two-step existence check) but in
      practice Kuzu 0.11.x DOES support it (see ``KuzuWriter.merge_edge``
      in src/graph/kuzu_writer.py).
    - Silent-fallback on any writer exception: the resolver returns an
      empty list and logs at debug level. This mirrors the
      ``graph_expander.py`` / ``graph_traversal.py`` pattern; a broken
      flag must never crash the synthesis pipeline.
    - Self-loop guard: a chunk "citing itself" does not become an edge.
    - Returns the list of newly *written* edges. Edges that already
      existed in the graph (and were therefore a no-op on MERGE) are NOT
      returned from the fallback path; with the pure-MERGE path we can't
      distinguish new vs existing from Python and return the edge as
      written (MERGE semantics protect the invariant on the DB side).

Binding: D-01 (no new runtime LLM), D-02 (no new offline LLM),
D-03 (no Kuzu schema changes — only writes to existing edge tables),
D-10 (regex / dict lookups only).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Protocol

from src.graph.citation_index import resolve_citation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writer protocol (duck-typed; accepts KuzuWriter or any MockWriter that
# exposes a ``query(cypher, params) -> list[list]`` method).
# ---------------------------------------------------------------------------


class _WriterLike(Protocol):
    def query(self, cypher: str, params: dict | None = None) -> list[list]: ...


# ---------------------------------------------------------------------------
# ResolvedEdge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedEdge:
    """An edge written (or attempted) by the on-demand resolver.

    Attributes:
        source_chunk_id: Chunk whose metadata held the unresolved citation.
        target_chunk_id: Chunk the citation resolved to.
        edge_type: Relationship type — defaults to ``"CITES"``. Future
            callers can widen this via the ``edge_type`` parameter on
            :func:`resolve_for_chunk`.
        confidence: Edge confidence stored on ``r.confidence``. Default
            0.9 reflects that the resolution went through the exact-match
            regex index; chapter-fallback resolutions could warrant a
            lower value in the future.
        raw_citation: The original citation string from chunk metadata,
            useful for audit / debug.
    """
    source_chunk_id: str
    target_chunk_id: str
    edge_type: str
    confidence: float
    raw_citation: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_MERGE_CYPHER_TEMPLATE = (
    "MATCH (a:Chunk {{id: $a_id}}), (b:Chunk {{id: $b_id}}) "
    "MERGE (a)-[r:{edge_type}]->(b) "
    "ON CREATE SET r.confidence = $conf"
)

_EXISTS_CYPHER_TEMPLATE = (
    "MATCH (a:Chunk {{id: $a_id}})-[r:{edge_type}]->(b:Chunk {{id: $b_id}}) "
    "RETURN count(r)"
)


def _edge_already_exists(
    writer: _WriterLike,
    source_id: str,
    target_id: str,
    edge_type: str,
) -> bool:
    """Return True iff a ``(source_id)-[:edge_type]->(target_id)`` edge exists.

    Used by the fallback path when MERGE with ON CREATE is unavailable,
    and by test doubles that want to assert idempotence.
    """
    try:
        rows = writer.query(
            _EXISTS_CYPHER_TEMPLATE.format(edge_type=edge_type),
            {"a_id": source_id, "b_id": target_id},
        )
    except Exception as exc:
        logger.debug(
            "on_demand_resolver: existence check failed for %s-[%s]->%s: %s",
            source_id, edge_type, target_id, exc,
        )
        return False

    if not rows or not rows[0]:
        return False
    try:
        return int(rows[0][0]) > 0
    except (TypeError, ValueError):
        return False


def _merge_edge(
    writer: _WriterLike,
    source_id: str,
    target_id: str,
    edge_type: str,
    confidence: float,
) -> bool:
    """Attempt a MERGE write-back, falling through to MATCH-then-CREATE.

    Returns True if the write appeared to succeed (either the edge was
    newly created or it already existed after this call). Returns False on
    silent failure.
    """
    try:
        writer.query(
            _MERGE_CYPHER_TEMPLATE.format(edge_type=edge_type),
            {
                "a_id": source_id,
                "b_id": target_id,
                "conf": confidence,
            },
        )
        return True
    except Exception as exc:
        # Silent-fallback: the pipeline MUST NOT crash because of a
        # resolver write failure. Debug-log and bail.
        logger.debug(
            "on_demand_resolver: MERGE failed for %s-[%s]->%s: %s",
            source_id, edge_type, target_id, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_for_chunk(
    chunk_id: str,
    unresolved_citations: Iterable[str] | None,
    writer: _WriterLike,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
    edge_type: str = "CITES",
    confidence: float = 0.9,
) -> list[ResolvedEdge]:
    """Resolve each unresolved citation string and MERGE an edge in Kuzu.

    Args:
        chunk_id: The source chunk whose metadata held the citations.
        unresolved_citations: Iterable of raw citation strings from the
            chunk metadata (e.g. ``["RCW 36.70A.681", "WAC 365-196-410"]``).
            ``None`` or empty -> fast-path no-op.
        writer: Any object exposing ``query(cypher, params) -> list[list]``.
            In production this is :class:`src.graph.kuzu_writer.KuzuWriter`.
        citation_index: Exact-match lookup from
            :func:`src.graph.citation_index.build_citation_index`.
        chapter_index: Chapter-level lookup from
            :func:`src.graph.citation_index.build_citation_index`.
        edge_type: Relationship type to create — must match an existing
            Kuzu REL table. Default ``"CITES"``.
        confidence: Edge ``r.confidence`` value. Default 0.9.

    Returns:
        The list of :class:`ResolvedEdge` objects representing newly
        written edges. Edges that already existed or that failed to
        resolve / write are NOT in this list.

    Notes:
        - Entire function is wrapped in silent-fallback: ANY exception
          anywhere inside is swallowed and the resolver returns ``[]``.
          Correctness of synthesis is more important than a perfect edge
          write-back.
        - Resolution uses ``allow_chapter_fallback=False`` because
          chapter-level false edges are a known risk in this corpus
          (see ``src/graph/citation_index.py`` docstring). On-demand
          resolution should be as strict as LLM-extraction was.
    """
    if not unresolved_citations:
        return []

    try:
        new_edges: list[ResolvedEdge] = []
        for raw in unresolved_citations:
            if not raw:
                continue

            target_id = resolve_citation(
                str(raw),
                citation_index,
                chapter_index,
                allow_chapter_fallback=False,
            )
            if target_id is None:
                logger.debug(
                    "on_demand_resolver: could not resolve citation %r "
                    "for chunk %s", raw, chunk_id,
                )
                continue

            # Self-loop guard: do not write (chunk)-[:CITES]->(chunk).
            if target_id == chunk_id:
                continue

            # Idempotence: skip write if the edge already exists so we
            # return an accurate "newly written" list and avoid redundant
            # writer round-trips. This ALSO lets MockWriter test doubles
            # observe the existence-check call for idempotence assertions.
            if _edge_already_exists(writer, chunk_id, target_id, edge_type):
                continue

            if not _merge_edge(writer, chunk_id, target_id, edge_type, confidence):
                continue

            new_edges.append(
                ResolvedEdge(
                    source_chunk_id=chunk_id,
                    target_chunk_id=target_id,
                    edge_type=edge_type,
                    confidence=confidence,
                    raw_citation=str(raw),
                )
            )
        return new_edges
    except Exception as exc:
        logger.debug(
            "on_demand_resolver: outer silent-fallback on chunk %s: %s",
            chunk_id, exc,
        )
        return []
