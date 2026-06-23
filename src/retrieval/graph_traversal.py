"""Kuzu graph traversal for citation chain expansion.

Follows CITES, IMPLEMENTS, SUBJECT_TO edges up to depth-2 from seed chunks.
Produces a flat ranked list for RRF fusion (per D-03) and graph_context
enrichment for final results (per D-14).

Functions:
    graph_traverse: Expand seed chunks via graph edges, return ranked results.
    rank_graph_results: Extract flat ordered chunk_id list from traversal results.
    get_graph_context: Get all relationship edges connected to a chunk.
"""

from __future__ import annotations

import logging

from src.config import (
    GRAPH_TRAVERSAL_DEPTH,
    GRAPH_TRAVERSAL_EDGE_TYPES,
    GRAPH_TRAVERSAL_MAX_RESULTS,
)

logger = logging.getLogger(__name__)

# Edge type priority for ranking within same depth (per D-03)
# Lower value = higher priority: IMPLEMENTS > SUBJECT_TO > CITES
EDGE_TYPE_PRIORITY = {"IMPLEMENTS": 0, "SUBJECT_TO": 1, "CITES": 2}

# Relationship types to query for graph_context enrichment (per D-14)
CONTEXT_EDGE_TYPES = ["CITES", "IMPLEMENTS", "SUBJECT_TO", "DEFINED_BY"]


def graph_traverse(
    writer,
    seed_ids: list[str],
    edge_types: list[str] | None = None,
    max_depth: int = GRAPH_TRAVERSAL_DEPTH,
    max_results: int = GRAPH_TRAVERSAL_MAX_RESULTS,
) -> list[tuple[str, int, str, float]]:
    """Expand seed chunks via graph edges up to max_depth hops (bidirectional).

    Traverses both outgoing and incoming edges so that seeds which are
    targets of relationships (not just sources) also discover connected
    chunks.

    Per D-03: Results form a flat ranked list. Ranking:
    1. depth-1 before depth-2
    2. Higher confidence first (within same depth)
    3. Edge type priority: IMPLEMENTS > SUBJECT_TO > CITES

    Per D-07: No agency filtering on graph edges -- cross-agency connections
    are the core value.

    Args:
        writer: KuzuWriter instance (already connected).
        seed_ids: Chunk IDs to expand from (union of vector + BM25 results).
        edge_types: Edge types to traverse. Defaults to config.GRAPH_TRAVERSAL_EDGE_TYPES.
        max_depth: Maximum hop depth (default 2).
        max_results: Cap on returned results (default 50, per pitfall #5).

    Returns:
        List of (chunk_id, depth, edge_type, confidence) tuples, sorted by
        D-03 priority, capped at max_results. Seed IDs are excluded.
    """
    if not seed_ids:
        return []

    if edge_types is None:
        edge_types = GRAPH_TRAVERSAL_EDGE_TYPES

    seed_set = set(seed_ids)
    # Track best discovery per chunk: chunk_id -> (depth, confidence, edge_type)
    best: dict[str, tuple[int, float, str]] = {}

    for edge_type in edge_types:
        for seed_id in seed_ids:
            # Depth 1: direct neighbors (outgoing edges)
            try:
                rows = writer.query(
                    f"MATCH (a:Chunk)-[r:{edge_type}]->(b:Chunk) "
                    f"WHERE a.id = $seed RETURN b.id, r.confidence",
                    {"seed": seed_id},
                )
            except Exception as e:
                logger.debug(
                    "Graph query failed for %s/%s: %s", edge_type, seed_id, e
                )
                rows = []

            for row in rows:
                cid, conf = row[0], float(row[1] or 0.0)
                if cid in seed_set:
                    continue  # Exclude seed chunks
                _update_best(best, cid, 1, conf, edge_type)

            # Depth 1: direct neighbors (incoming edges — bidirectional)
            try:
                rows = writer.query(
                    f"MATCH (a:Chunk)<-[r:{edge_type}]-(b:Chunk) "
                    f"WHERE a.id = $seed RETURN b.id, r.confidence",
                    {"seed": seed_id},
                )
            except Exception as e:
                logger.debug(
                    "Graph incoming query failed for %s/%s: %s",
                    edge_type, seed_id, e,
                )
                rows = []

            for row in rows:
                cid, conf = row[0], float(row[1] or 0.0)
                if cid in seed_set:
                    continue
                _update_best(best, cid, 1, conf, edge_type)

            # Depth 2: two-hop neighbors (outgoing)
            if max_depth >= 2:
                try:
                    rows = writer.query(
                        f"MATCH (a:Chunk)-[:{edge_type}]->(mid:Chunk)"
                        f"-[r:{edge_type}]->(b:Chunk) "
                        f"WHERE a.id = $seed RETURN b.id, r.confidence",
                        {"seed": seed_id},
                    )
                except Exception as e:
                    logger.debug(
                        "Graph depth-2 query failed for %s/%s: %s",
                        edge_type,
                        seed_id,
                        e,
                    )
                    rows = []

                for row in rows:
                    cid, conf = row[0], float(row[1] or 0.0)
                    if cid in seed_set:
                        continue
                    _update_best(best, cid, 2, conf, edge_type)

                # Depth 2: two-hop neighbors (incoming)
                try:
                    rows = writer.query(
                        f"MATCH (a:Chunk)<-[:{edge_type}]-(mid:Chunk)"
                        f"<-[r:{edge_type}]-(b:Chunk) "
                        f"WHERE a.id = $seed RETURN b.id, r.confidence",
                        {"seed": seed_id},
                    )
                except Exception as e:
                    logger.debug(
                        "Graph depth-2 incoming query failed for %s/%s: %s",
                        edge_type,
                        seed_id,
                        e,
                    )
                    rows = []

                for row in rows:
                    cid, conf = row[0], float(row[1] or 0.0)
                    if cid in seed_set:
                        continue
                    _update_best(best, cid, 2, conf, edge_type)

    # Sort by D-03 priority: depth ASC, confidence DESC, edge type priority ASC
    results = [
        (cid, depth, etype, conf) for cid, (depth, conf, etype) in best.items()
    ]
    results.sort(
        key=lambda x: (x[1], -x[3], EDGE_TYPE_PRIORITY.get(x[2], 99))
    )

    return results[:max_results]


def _update_best(
    best: dict[str, tuple[int, float, str]],
    cid: str,
    depth: int,
    conf: float,
    edge_type: str,
) -> None:
    """Update the best discovery for a chunk if this path is better.

    Better means: lower depth, then higher confidence, then better edge type priority.
    """
    new_key = (depth, -conf, EDGE_TYPE_PRIORITY.get(edge_type, 99))
    if cid not in best:
        best[cid] = (depth, conf, edge_type)
        return
    existing = best[cid]
    existing_key = (
        existing[0],
        -existing[1],
        EDGE_TYPE_PRIORITY.get(existing[2], 99),
    )
    if new_key < existing_key:
        best[cid] = (depth, conf, edge_type)


def rank_graph_results(
    traversal_results: list[tuple[str, int, str, float]],
) -> list[str]:
    """Extract flat ordered chunk_id list from traversal results for RRF.

    The traversal results are already sorted by D-03 priority.
    This just extracts the chunk_ids in order.

    Args:
        traversal_results: Output of graph_traverse().

    Returns:
        List of chunk IDs in ranked order.
    """
    return [cid for cid, _, _, _ in traversal_results]


def get_graph_context(writer, chunk_id: str) -> list[dict] | None:
    """Get all relationship edges connected to a chunk.

    Per D-14: Returns list of {chunk_id, citation, rel_type, direction}
    for the graph_context field of RetrievalResult.

    Args:
        writer: KuzuWriter instance.
        chunk_id: The chunk to get context for.

    Returns:
        List of edge dicts, or None if no edges found.
    """
    context: list[dict] = []
    for rel_type in CONTEXT_EDGE_TYPES:
        # Outgoing edges
        try:
            for row in writer.query(
                f"MATCH (a:Chunk)-[r:{rel_type}]->(b:Chunk) "
                f"WHERE a.id = $cid RETURN b.id, b.citation",
                {"cid": chunk_id},
            ):
                context.append(
                    {
                        "chunk_id": row[0],
                        "citation": row[1] or "",
                        "rel_type": rel_type,
                        "direction": "outgoing",
                    }
                )
        except Exception:
            pass

        # Incoming edges
        try:
            for row in writer.query(
                f"MATCH (a:Chunk)<-[r:{rel_type}]-(b:Chunk) "
                f"WHERE a.id = $cid RETURN b.id, b.citation",
                {"cid": chunk_id},
            ):
                context.append(
                    {
                        "chunk_id": row[0],
                        "citation": row[1] or "",
                        "rel_type": rel_type,
                        "direction": "incoming",
                    }
                )
        except Exception:
            pass

    return context if context else None
