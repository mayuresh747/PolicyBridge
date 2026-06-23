"""Hybrid retriever: vector + BM25 + graph with linear fusion.

Primary entry point for Phase 4 (Query Pipeline).
Per D-12: retrieve(query, agency_filter, top_k) -> list[RetrievalResult]
Fusion: min-max normalized linear fusion (vector 0.55, bm25 0.45).
Graph traversal feeds the post-retrieval expand_by_graph stage; graph
results are NOT included in fusion (BFS rank is incommensurable with
similarity scores).
Per D-06: Agency filter pre-filters vector and BM25.
Per D-07: Graph traversal allows cross-agency edges from filtered seeds.
Per D-14: Graph context enrichment included inline on each result.
"""

import logging
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd

from src.config import (
    BM25_TOP_K,
    FUSION_WEIGHTS,
    GRAPH_EXPAND_WEIGHTS,
    GRAPH_FEATURE_BEAM_TRAVERSAL,
    GRAPH_FEATURE_PROFILES,
    GRAPH_TRAVERSAL_DEPTH,
    GRAPH_TRAVERSAL_EDGE_TYPES,
    KUZU_PATH,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
    RETRIEVAL_TOP_K,
    VECTOR_TOP_K,
)
from src.graph.kuzu_writer import KuzuWriter
from src.retrieval.bm25_search import bm25_search
from src.retrieval.fusion import linear_fuse
from src.retrieval.graph_traversal import (
    get_graph_context,
    graph_traverse,
    rank_graph_results,
)
from src.retrieval.models import RetrievalResult
from src.retrieval.vector_search import vector_search

logger = logging.getLogger(__name__)


def build_citation_path(row: dict) -> dict:
    """Parse citation_path from chunk metadata fields.

    No extra DB query needed -- all fields exist on the ChunkRecord.

    Args:
        row: Dict-like object with agency, citation, section_number,
            subsection_id, and parent_section fields.

    Returns:
        Dict with keys: agency, document, section, subsection.
    """
    agency = row.get("agency", "") or ""
    citation = row.get("citation", "") or ""
    section = row.get("section_number", "") or ""
    subsection = row.get("subsection_id", None)
    parent = row.get("parent_section", "") or ""
    parts = citation.split(" ", 1) if citation else ["", ""]

    return {
        "agency": agency,
        "document": parent or (
            parts[1].rsplit(".", 1)[0]
            if len(parts) > 1 and "." in parts[1]
            else citation
        ),
        "section": section,
        "subsection": subsection,
    }


def retrieve(
    query: str,
    agency_filter: list[str] | None = None,
    top_k: int = RETRIEVAL_TOP_K,
    lancedb_path: str | Path | None = None,
    kuzu_path: str | Path | None = None,
    return_breakdown: bool = False,
    return_query_vec: bool = False,
) -> (
    list[RetrievalResult]
    | tuple[list[RetrievalResult], dict]
    | tuple[list[RetrievalResult], "np.ndarray"]
    | tuple[list[RetrievalResult], dict, "np.ndarray"]
):
    """Execute hybrid retrieval: vector + BM25 + graph, merged via RRF.

    Per D-12: Primary entry point for the retrieval engine.
    Fusion: min-max normalized linear fusion (vector 0.55, bm25 0.45).
    Graph traversal results feed the expand_by_graph expansion stage in
    pipeline.py; they do not participate in fusion.
    Per D-06: Agency filter pre-filters vector and BM25.
    Per D-07: Graph traversal allows cross-agency edges from filtered seeds.

    Args:
        query: Natural language query string.
        agency_filter: List of agency names to scope search. None = all
            agencies (per D-08).
        top_k: Number of results to return (default 15).
        lancedb_path: Override LanceDB path (for testing). Defaults to
            config.LANCEDB_PATH.
        kuzu_path: Override Kuzu path (for testing). Defaults to
            config.KUZU_PATH.
        return_breakdown: If True, include a per-source breakdown dict.
        return_query_vec: If True, also return the L2-normalised query
            embedding that vector_search already computed.  Used by
            solve_tree to cache the vector on each TreeNode leaf so
            downstream consumers (S3 seed fusion) can reuse it without
            re-embedding (Phase 8 D-06 binding).

    Returns:
        Depending on flags:
            - default                        -> list[RetrievalResult]
            - return_breakdown=True          -> (results, breakdown)
            - return_query_vec=True          -> (results, query_vec)
            - both flags True                -> (results, breakdown, query_vec)

        ``query_vec`` is ``np.ndarray | None`` — ``None`` if vector_search
        did not run / returned no vector (treated as a graceful fallback
        by callers).
    """
    _lancedb_path = Path(lancedb_path) if lancedb_path else LANCEDB_PATH
    _kuzu_path = Path(kuzu_path) if kuzu_path else KUZU_PATH

    # Connect to LanceDB
    db = lancedb.connect(str(_lancedb_path))
    table = db.open_table(LANCEDB_TABLE_NAME)

    # Step 1: Vector search (per D-06: pre-filtered by agency)
    # Per D-05: reuse the query embedding vector_search already computes so
    # downstream consumers (beam traversal under GRAPH_FEATURE_BEAM_TRAVERSAL)
    # never trigger a second embedding call.  query_vec is L2-normalized
    # np.float32 shape (EMBEDDING_DIMENSIONS,).
    logger.info("Running vector search for: %s", query[:80])
    vec_df, query_vec = vector_search(
        table,
        query,
        agency_filter=agency_filter,
        top_k=VECTOR_TOP_K,
        return_query_vec=True,
    )
    vec_ids = vec_df["id"].tolist() if not vec_df.empty else []
    # Convert cosine distance (lower=better) to similarity (higher=better) for linear_fuse
    if not vec_df.empty and "_distance" in vec_df.columns:
        vec_scored: list[tuple[str, float]] = list(
            zip(vec_df["id"].tolist(), (1 - vec_df["_distance"]).tolist())
        )
    else:
        vec_scored = [(cid, 0.5) for cid in vec_ids]

    vec_breakdown = []
    if return_breakdown and not vec_df.empty:
        for _, row in vec_df.head(5).iterrows():
            # Use 1 - distance for display consistency
            raw = row.get("_distance", None)
            display_score = round(float(1 - raw), 4) if raw is not None else 0.0
            vec_breakdown.append({
                "citation": str(row.get("citation", "")),
                "score": display_score,
                "agency": str(row.get("agency", "")),
            })

    # Step 2: BM25 search (per D-06: pre-filtered by agency)
    logger.info("Running BM25 search for: %s", query[:80])
    bm25_df = bm25_search(
        table, query, agency_filter=agency_filter, top_k=BM25_TOP_K
    )
    bm25_ids = bm25_df["id"].tolist() if not bm25_df.empty else []
    if not bm25_df.empty and "_score" in bm25_df.columns:
        bm25_scored: list[tuple[str, float]] = list(
            zip(bm25_df["id"].tolist(), bm25_df["_score"].tolist())
        )
    else:
        bm25_scored = [(cid, 0.5) for cid in bm25_ids]

    bm25_breakdown = []
    if return_breakdown and not bm25_df.empty:
        for _, row in bm25_df.head(5).iterrows():
            bm25_breakdown.append({
                "citation": str(row.get("citation", "")),
                "score": round(float(row.get("_score", row.get("score", 0))), 4),
                "agency": str(row.get("agency", "")),
            })

    # Step 3: Graph traversal (per D-04: starting from union of vec+bm25 seeds)
    # When GRAPH_FEATURE_BEAM_TRAVERSAL is enabled, dispatch to the S2 scored
    # beam (src/graph/beam_traversal.py) using the query_vec already computed
    # by vector_search above.  Per D-05 no new embedding call is made here.
    # On ANY failure in the beam path, fall back silently to the legacy BFS.
    graph_ids: list[str] = []
    if _kuzu_path.exists():
        try:
            with KuzuWriter(_kuzu_path) as writer:
                # Deduplicated, order-preserving union of seeds
                seed_ids = list(dict.fromkeys(vec_ids + bm25_ids))

                used_beam = False
                if GRAPH_FEATURE_BEAM_TRAVERSAL and seed_ids:
                    # Lazy import so the legacy path remains importable even
                    # if the beam module has a problem.
                    from src.graph.beam_traversal import beam_traverse
                    from src.graph.traversal_profiles import (
                        TraversalProfile,
                        profile_for,
                    )

                    try:
                        if GRAPH_FEATURE_PROFILES:
                            profile = profile_for(query, None)
                        else:
                            profile = TraversalProfile(
                                name="default",
                                edge_types=list(GRAPH_TRAVERSAL_EDGE_TYPES),
                                max_depth=GRAPH_TRAVERSAL_DEPTH,
                                edge_weights={
                                    e: GRAPH_EXPAND_WEIGHTS.get(e, 1.0)
                                    for e in GRAPH_TRAVERSAL_EDGE_TYPES
                                },
                            )
                        # Reuse the vector_search query embedding directly
                        # (D-05 binding: no new embed call here).
                        paths = beam_traverse(
                            writer,
                            seed_ids,
                            profile,
                            query_vec,
                            lancedb_path=_lancedb_path,
                        )
                        graph_ids = [p.chunk_id for p in paths]
                        used_beam = True
                        logger.info(
                            "Beam traversal: seed_ids=%d, graph_ids=%d",
                            len(seed_ids), len(graph_ids),
                        )
                    except Exception as beam_exc:
                        logger.warning(
                            "Beam traversal failed, falling back to legacy "
                            "BFS: %s",
                            beam_exc,
                        )

                if not used_beam:
                    traversal = graph_traverse(writer, seed_ids)
                    graph_ids = rank_graph_results(traversal)
                    logger.info(
                        "Graph traversal: seed_ids=%d, graph_ids=%d",
                        len(seed_ids), len(graph_ids),
                    )
                    if not graph_ids:
                        # Diagnostic: check if seed IDs exist in Kuzu at all.
                        # If zero overlap, Kuzu and LanceDB were built from
                        # different ingestion runs (different UUIDs).
                        try:
                            sample_seeds = seed_ids[:5]
                            found_in_kuzu = 0
                            for sid in sample_seeds:
                                rows = writer.query(
                                    "MATCH (c:Chunk) WHERE c.id = $cid RETURN c.id",
                                    {"cid": sid},
                                )
                                if rows:
                                    found_in_kuzu += 1
                            if found_in_kuzu == 0:
                                logger.warning(
                                    "Graph ID mismatch: 0/%d seed IDs found in Kuzu. "
                                    "LanceDB and Kuzu were likely built from different "
                                    "ingestion runs. Run: python scripts/run_graph.py "
                                    "--mode full --use-regex",
                                    len(sample_seeds),
                                )
                            else:
                                # Seeds exist but no edges -- log edge counts
                                for etype in ["CITES", "IMPLEMENTS", "SUBJECT_TO"]:
                                    count_rows = writer.query(
                                        f"MATCH (:Chunk)-[r:{etype}]->(:Chunk) RETURN count(r)"
                                    )
                                    count = count_rows[0][0] if count_rows else 0
                                    logger.info("Graph edge count for %s: %d", etype, count)
                        except Exception as e2:
                            logger.debug("Graph diagnostic check failed: %s", e2)
        except Exception as e:
            logger.warning(
                "Graph traversal failed (continuing without): %s", e
            )
    else:
        logger.info(
            "Kuzu graph not found at %s -- skipping graph traversal",
            _kuzu_path,
        )

    # Step 4: Linear fusion of vector + BM25 (graph is a post-retrieval expansion
    # stage in pipeline.py, not part of fusion — graph BFS rank is not
    # commensurable with similarity-based scores).
    ranked_lists: dict[str, list[tuple[str, float]]] = {}
    if vec_scored:
        ranked_lists["vector"] = vec_scored
    if bm25_scored:
        ranked_lists["bm25"] = bm25_scored

    if not ranked_lists:
        logger.warning(
            "No results from any search path for query: %s", query[:80]
        )
        if return_breakdown and return_query_vec:
            return [], {"vector": [], "bm25": []}, query_vec
        if return_breakdown:
            return [], {"vector": [], "bm25": []}
        if return_query_vec:
            return [], query_vec
        return []

    fused = linear_fuse(ranked_lists, weights=FUSION_WEIGHTS)
    top_fused = fused[:top_k]

    # Step 5: Build metadata lookup from existing DataFrames
    # Merge vec_df and bm25_df for metadata, avoiding full-table scan
    metadata_dfs: list[pd.DataFrame] = []
    if not vec_df.empty:
        metadata_dfs.append(vec_df)
    if not bm25_df.empty:
        metadata_dfs.append(bm25_df)

    if metadata_dfs:
        all_meta = pd.concat(metadata_dfs, ignore_index=True).drop_duplicates(
            subset=["id"]
        )
        meta_lookup: dict[str, pd.Series] = {
            row["id"]: row for _, row in all_meta.iterrows()
        }
    else:
        meta_lookup = {}

    # For chunks found only via graph, fetch metadata from LanceDB
    missing_ids = [cid for cid, _, _ in top_fused if cid not in meta_lookup]
    if missing_ids:
        try:
            ids_str = ", ".join(f"'{cid}'" for cid in missing_ids)
            extra = (
                table.search()
                .where(f"id IN ({ids_str})")
                .limit(len(missing_ids))
                .to_pandas()
            )
            for _, row in extra.iterrows():
                meta_lookup[row["id"]] = row
        except Exception as e:
            logger.warning(
                "Failed to fetch graph-only chunk metadata: %s", e
            )

    # Step 6: Build RetrievalResult objects with citation_path and graph_context
    results: list[RetrievalResult] = []

    # Open graph connection once for graph_context enrichment (per D-14)
    graph_writer: KuzuWriter | None = None
    if _kuzu_path.exists():
        try:
            graph_writer = KuzuWriter(_kuzu_path)
        except Exception:
            pass

    try:
        for chunk_id, score, sources in top_fused:
            row = meta_lookup.get(chunk_id)
            if row is None:
                logger.debug(
                    "Skipping chunk %s -- no metadata available", chunk_id
                )
                continue

            # Citation path (per D-14, RET-04)
            row_dict = (
                row.to_dict() if hasattr(row, "to_dict") else dict(row)
            )
            cpath = build_citation_path(row_dict)

            # Graph context enrichment (per D-14)
            gctx = None
            if graph_writer:
                try:
                    gctx = get_graph_context(graph_writer, chunk_id)
                except Exception:
                    pass

            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    text=str(row_dict.get("text", "")),
                    score=score,
                    citation=str(row_dict.get("citation", "")),
                    section_title=row_dict.get("section_title"),
                    agency=str(row_dict.get("agency", "")),
                    authority_level=str(row_dict.get("authority_level", "")),
                    document_type=str(row_dict.get("document_type", "")),
                    retrieval_sources=sources,
                    graph_context=gctx,
                    citation_path=cpath,
                )
            )
    finally:
        if graph_writer:
            try:
                graph_writer.close()
            except Exception:
                pass

    if return_breakdown and return_query_vec:
        breakdown = {
            "vector": vec_breakdown,
            "bm25": bm25_breakdown,
        }
        return results, breakdown, query_vec
    if return_breakdown:
        breakdown = {
            "vector": vec_breakdown,
            "bm25": bm25_breakdown,
        }
        return results, breakdown
    if return_query_vec:
        return results, query_vec
    return results
