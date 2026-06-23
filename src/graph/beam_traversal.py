"""S2: beam / relevance-gated graph traversal.

Replaces the blind BFS in ``src/retrieval/graph_traversal.py`` with a scored
beam walk. Kuzu round-trips stay on the same order of magnitude (batched per
edge type per hop) but each hop keeps only the top-B neighbours scored by:

    score = cosine(query_vec, neighbour_vec)
          x edge_weight[edge_type]
          x depth_decay[depth_index]
          x hub_penalty(neighbour)

    hub_penalty(n) = 1 / (1 + alpha * log(1 + in_degree(n)))

Reuses the existing ``query_vec`` computed upstream - NO new embedding calls
in this module (D-01 / D-05). ``query_vec`` is supplied by the caller, which
lifts it from ``vector_search``'s return value. Falls back silently to ``[]``
on any Kuzu / LanceDB failure; the caller is responsible for routing back
to the legacy BFS in that case.

Out of scope per D-04:
    - The conflict edge family is never a member of any profile's
      ``edge_types``; this module does not query it and does not treat it
      specially.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import lancedb
import numpy as np

from src.config import (
    GRAPH_BEAM_DEPTH_DECAY,
    GRAPH_BEAM_HUB_PENALTY_ALPHA,
    GRAPH_BEAM_WIDTH,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
)
from src.graph.traversal_profiles import TraversalProfile

logger = logging.getLogger(__name__)


# Edge types considered for the in-degree (hub) penalty.  These are the
# directed semantic edges the KG currently writes.  The conflict edge family
# is intentionally omitted (empty table, D-04).
_HUB_EDGE_TYPES = ["CITES", "IMPLEMENTS", "SUBJECT_TO", "DEFINED_BY", "AMENDED_BY"]


@dataclass
class ScoredPath:
    """A single scored path emitted by the beam.

    Attributes:
        chunk_id: The terminal chunk this path points at.
        score: Final composite score (higher = better).
        depth: Hop count from seed (1 = direct neighbour, 2 = two-hop, ...).
        edge_type: The edge type on the final hop that led to ``chunk_id``.
        seed_id: The original seed this path originated from.
        path: Full trail of ``(edge_type, intermediate_chunk_id)`` tuples from
            the seed to (but not including) ``chunk_id``.  For a depth-1 path
            this is ``[(edge_type, seed_id)]``.
    """

    chunk_id: str
    score: float
    depth: int
    edge_type: str
    seed_id: str
    path: list[tuple[str, str]] = field(default_factory=list)


def _fetch_embeddings(
    lancedb_path: Path,
    chunk_ids: list[str],
) -> dict[str, np.ndarray]:
    """Batch-fetch embeddings for ``chunk_ids`` from LanceDB.

    Mirrors the pattern in ``graph_expander._batch_embedding_fetch``.  Returns
    a map of ``chunk_id -> L2-normalised np.float32 vector``.  Missing ids are
    simply absent from the returned dict.  Any failure returns ``{}``.
    """
    if not chunk_ids:
        return {}
    try:
        db = lancedb.connect(str(lancedb_path))
        table = db.open_table(LANCEDB_TABLE_NAME)
        ids_sql = ", ".join(f"'{cid}'" for cid in chunk_ids)
        df = (
            table.search()
            .where(f"id IN ({ids_sql})")
            .limit(len(chunk_ids))
            .select(["id", "embedding"])
            .to_pandas()
        )
    except Exception as exc:
        logger.warning("Beam: LanceDB embedding fetch failed: %s", exc)
        return {}

    out: dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        v = np.asarray(row["embedding"], dtype=np.float32)
        n = float(np.linalg.norm(v))
        if n > 0:
            out[str(row["id"])] = v / n
    return out


def _fetch_in_degrees(writer, chunk_ids: list[str]) -> dict[str, int]:
    """Return in-degree (across all semantic edge types) for each chunk.

    Single Kuzu round-trip using a multi-label rel pattern
    ``[:CITES|IMPLEMENTS|SUBJECT_TO|DEFINED_BY|AMENDED_BY]``.  If Kuzu
    rejects the multi-label form, falls back to per-edge-type queries and
    accumulates.  Failures return ``{}`` (hub penalty collapses to 1 -
    neutral).
    """
    if not chunk_ids:
        return {}
    ids_csv = ", ".join(f"'{cid}'" for cid in chunk_ids)
    rel_union = "|".join(_HUB_EDGE_TYPES)
    counts: dict[str, int] = {cid: 0 for cid in chunk_ids}

    try:
        rows = writer.query(
            f"MATCH (a:Chunk)-[:{rel_union}]->(b:Chunk) "
            f"WHERE b.id IN [{ids_csv}] "
            f"RETURN b.id, count(*)"
        )
    except Exception as exc:
        logger.debug("Beam: unioned in-degree query failed: %s; "
                     "falling back to per-edge-type accumulation", exc)
        rows = None

    if rows is not None:
        for row in rows or []:
            try:
                cid = str(row[0])
                n = int(row[1])
            except (IndexError, TypeError, ValueError):
                continue
            # Overwrite rather than accumulate - this is the single unioned
            # query's authoritative count.
            counts[cid] = n
        return counts

    # Fallback path: one query per edge type, accumulate.
    for et in _HUB_EDGE_TYPES:
        try:
            rows = writer.query(
                f"MATCH (a:Chunk)-[:{et}]->(b:Chunk) "
                f"WHERE b.id IN [{ids_csv}] "
                f"RETURN b.id, count(*)"
            )
        except Exception as exc:
            logger.debug("Beam: in-degree query failed for %s: %s", et, exc)
            rows = []
        for row in rows or []:
            try:
                cid = str(row[0])
                n = int(row[1])
            except (IndexError, TypeError, ValueError):
                continue
            counts[cid] = counts.get(cid, 0) + n
    return counts


def _hub_penalty(in_degree: int, alpha: float) -> float:
    """hub_penalty(n) = 1 / (1 + alpha * log(1 + in_degree))."""
    return 1.0 / (1.0 + alpha * math.log(1.0 + max(0, int(in_degree))))


def _depth_factor(depth_index: int, decay: list[float]) -> float:
    """Return ``decay[depth_index]`` or the last element if out of range."""
    if not decay:
        return 1.0
    if depth_index < 0:
        return decay[0]
    if depth_index >= len(decay):
        return decay[-1]
    return float(decay[depth_index])


def beam_traverse(
    writer,
    seeds: list[str],
    profile: TraversalProfile,
    query_vec: np.ndarray,
    width: int = GRAPH_BEAM_WIDTH,
    lancedb_path: Path | None = None,
) -> list[ScoredPath]:
    """Scored BFS with per-hop top-B pruning.

    Args:
        writer: Open KuzuWriter (or compatible object exposing
            ``.query(cypher, params=None)``).  The caller owns its lifecycle.
        seeds: Seed chunk ids (union of vector + BM25 hits upstream).
        profile: ``TraversalProfile`` controlling edge types, depth, weights.
        query_vec: L2-normalised query embedding (shape ``(D,)``).  MUST be
            computed upstream (reuse ``vector_search``'s result) - this module
            does NOT embed anything (D-05).
        width: Per-hop beam width.  Defaults to ``GRAPH_BEAM_WIDTH``.
        lancedb_path: Override for testing.  Defaults to ``LANCEDB_PATH``.

    Returns:
        ``list[ScoredPath]`` sorted by ``score`` descending.  Seeds are
        excluded.  Empty list on any catastrophic failure.
    """
    # --- Argument sanity --------------------------------------------------
    if not seeds:
        return []
    if query_vec is None or getattr(query_vec, "size", 0) == 0:
        return []
    if not profile.edge_types or profile.max_depth < 1:
        return []

    qv = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(qv))
    if qn > 0:
        qv = qv / qn

    _lancedb_path = Path(lancedb_path) if lancedb_path else LANCEDB_PATH
    alpha = float(GRAPH_BEAM_HUB_PENALTY_ALPHA)
    decay = list(GRAPH_BEAM_DEPTH_DECAY) or [1.0]

    seed_set = set(seeds)
    # best[chunk_id] -> ScoredPath with the highest score observed so far
    best: dict[str, ScoredPath] = {}

    # Frontier starts as the seeds themselves; each iteration expands them.
    # Each frontier entry: (current_chunk_id, trail, seed_of_origin)
    frontier: list[tuple[str, list[tuple[str, str]], str]] = [
        (sid, [], sid) for sid in seeds
    ]

    try:
        for hop in range(profile.max_depth):
            if not frontier:
                break
            depth = hop + 1  # hop 0 -> depth-1 neighbours
            depth_factor = _depth_factor(hop, decay)

            # --- Pull all candidates at this hop, per edge type --------
            # Map: neighbour_id -> list of (score_so_far_excl_hub, edge_type, trail, seed)
            candidates: dict[
                str, list[tuple[float, str, list[tuple[str, str]], str]]
            ] = {}
            current_ids = [f[0] for f in frontier]
            ids_csv = ", ".join(f"'{cid}'" for cid in current_ids)

            for edge_type in profile.edge_types:
                weight = float(profile.edge_weights.get(edge_type, 1.0))
                try:
                    rows = writer.query(
                        f"MATCH (s:Chunk)-[r:{edge_type}]->(n:Chunk) "
                        f"WHERE s.id IN [{ids_csv}] "
                        f"RETURN s.id, n.id, r.confidence"
                    )
                except Exception as exc:
                    logger.debug(
                        "Beam: Kuzu %s query failed: %s", edge_type, exc
                    )
                    rows = []

                # Map frontier current_id -> (trail, seed_of_origin)
                frontier_meta: dict[str, tuple[list[tuple[str, str]], str]] = {
                    f[0]: (f[1], f[2]) for f in frontier
                }

                for row in rows or []:
                    try:
                        src_id = str(row[0])
                        neighbour_id = str(row[1])
                    except (IndexError, TypeError):
                        continue
                    if neighbour_id in seed_set:
                        continue
                    meta = frontier_meta.get(src_id)
                    if meta is None:
                        continue
                    trail, seed_of = meta
                    new_trail = trail + [(edge_type, src_id)]
                    candidates.setdefault(neighbour_id, []).append(
                        (weight, edge_type, new_trail, seed_of)
                    )

            if not candidates:
                break

            # --- Batch-fetch embeddings + in-degrees for all neighbours --
            neighbour_ids = list(candidates.keys())
            vec_map = _fetch_embeddings(_lancedb_path, neighbour_ids)
            in_deg = _fetch_in_degrees(writer, neighbour_ids)

            # --- Score candidates --------------------------------------
            scored: list[ScoredPath] = []
            for nid, variants in candidates.items():
                vec_n = vec_map.get(nid)
                if vec_n is None:
                    # No embedding available; skip (conservative - can't score)
                    continue
                cosine = float(np.dot(qv, vec_n))
                hub_pen = _hub_penalty(in_deg.get(nid, 0), alpha)
                # Pick the best (weight, edge_type, trail, seed) for this nid
                best_variant = max(variants, key=lambda v: v[0])
                weight, etype, trail, seed_of = best_variant
                score = cosine * weight * depth_factor * hub_pen
                scored.append(
                    ScoredPath(
                        chunk_id=nid,
                        score=score,
                        depth=depth,
                        edge_type=etype,
                        seed_id=seed_of,
                        path=list(trail),
                    )
                )

            # --- Prune to top-width at this hop -------------------------
            # Beam semantics: keep only top-B by score at each hop, both for
            # the final output and for the next hop's frontier.
            scored.sort(key=lambda s: -s.score)
            top = scored[: max(1, int(width))]

            # --- Merge pruned set into global best ---------------------
            for sp in top:
                prev = best.get(sp.chunk_id)
                if prev is None or sp.score > prev.score:
                    best[sp.chunk_id] = sp

            # Next frontier: top candidates at this hop become the new
            # source nodes for the next hop's outgoing queries.
            frontier = [
                (sp.chunk_id, sp.path + [(sp.edge_type, sp.chunk_id)], sp.seed_id)
                for sp in top
            ]

    except Exception as exc:
        logger.warning(
            "Beam traversal hit catastrophic error; returning []: %s", exc
        )
        return []

    # --- Final sort: global top by score -----------------------------------
    final = sorted(best.values(), key=lambda s: -s.score)
    return final
