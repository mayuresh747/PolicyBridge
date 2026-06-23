"""Embedding-based rerankers for the query pipeline.

``rerank_by_answer`` (L3+): embeds the tree answer from solve_tree() and
reranks chunks by cosine similarity. Chunks closest to the actual answer rise
above keyword-match noise.

``rerank_by_query`` (L1/L2): embeds the query and reranks chunks by cosine
similarity before synthesis. Gives L1/L2 the same second-pass scoring that
L3+ receives via rerank_by_answer.

Both share ``_fetch_chunk_embeddings`` for the LanceDB vector-fetch step.

The per-level SYNTHESIS_TOP_K budget (config.py) caps how many chunks
reach GPT-5.1 synthesis.
"""

from __future__ import annotations

import logging
from pathlib import Path

import lancedb
import numpy as np

from src.config import LANCEDB_PATH, LANCEDB_TABLE_NAME, RETRIEVAL_TOP_K, SYNTHESIS_TOP_K
from src.embeddings.openai_embedder import embed_texts_sync
from src.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


def _fetch_chunk_embeddings(
    chunk_ids: list[str],
    lancedb_path: Path | None = None,
) -> dict[str, np.ndarray]:
    """Fetch and L2-normalize stored embeddings for the given chunk IDs.

    Performs a scan-based (not ANN) fetch so that exact vectors are returned
    for a specific small set of chunk IDs. The caller's working set is already
    small (~15-120 chunks), so a full-table scan filtered by WHERE is correct.

    Args:
        chunk_ids: List of chunk UUIDs to fetch embeddings for.
        lancedb_path: Override LanceDB path (for testing).

    Returns:
        Dict mapping chunk_id to its L2-normalized embedding vector. Chunks
        without a stored embedding (e.g., cache-only chunks) are omitted.

    Raises:
        Exception: Propagated if LanceDB connection or table open fails.
    """
    _lancedb_path = Path(lancedb_path) if lancedb_path else LANCEDB_PATH
    db = lancedb.connect(str(_lancedb_path))
    table = db.open_table(LANCEDB_TABLE_NAME)
    ids_str = ", ".join(f"'{cid}'" for cid in chunk_ids)
    vec_df = (
        table.search()
        .where(f"id IN ({ids_str})")
        .limit(len(chunk_ids))
        .select(["id", "embedding"])
        .to_pandas()
    )
    vec_map: dict[str, np.ndarray] = {}
    for _, row in vec_df.iterrows():
        v = np.array(row["embedding"], dtype=np.float32)
        v_norm = np.linalg.norm(v)
        if v_norm > 0:
            vec_map[str(row["id"])] = v / v_norm
    return vec_map


def rerank_by_answer(
    tree_answer: str,
    results: list[RetrievalResult],
    level: str,
    lancedb_path: Path | None = None,
    audit_mode: bool = False,
) -> list[RetrievalResult] | tuple[list[RetrievalResult], dict]:
    """Rerank chunks by cosine similarity to the tree answer embedding.

    Embeds tree_answer via text-embedding-3-large, fetches stored embeddings
    for all chunks in results from LanceDB, computes cosine similarity, and
    returns the top-N chunks per SYNTHESIS_TOP_K[level].

    Args:
        tree_answer: Merged LLM-generated answer text from solve_tree().
        results: Deduplicated RetrievalResult objects from all leaves
            (including session cache chunks if any).
        level: Query complexity level (L1-L6) for budget lookup.
        lancedb_path: Override LanceDB path (for testing).
        audit_mode: If True, return tuple of (reranked_results, audit_data).

    Returns:
        Reranked list of RetrievalResult, capped at SYNTHESIS_TOP_K[level].
        Scores updated to cosine similarity (0.0-1.0 scale).
        Falls back to top-budget by original RRF score on any failure.
        If audit_mode=True, returns (reranked_list, audit_data_dict).
    """
    budget = SYNTHESIS_TOP_K.get(level, RETRIEVAL_TOP_K)

    if not results:
        if audit_mode:
            return results, {"method": "answer_embedding", "before_count": 0, "after_count": 0, "kept": [], "dropped": [], "dropped_total": 0}
        return results

    # --- Capture before state for audit --------------------------------
    before_order: list[tuple[str, str, float]] = [
        (r.chunk_id, r.citation, r.score) for r in results
    ]

    # --- Embed the answer ------------------------------------------------
    try:
        raw_vec = embed_texts_sync([tree_answer[:8000]])[0]
        answer_vec = np.array(raw_vec, dtype=np.float32)
        norm = np.linalg.norm(answer_vec)
        if norm == 0:
            logger.warning("Answer embedding is zero vector, falling back to RRF ranking")
            fallback_result = _fallback(results, budget)
            if audit_mode:
                return fallback_result, {"method": "answer_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
            return fallback_result
        answer_vec = answer_vec / norm
    except Exception as exc:
        logger.warning(
            "Answer embedding failed, returning top-%d by RRF score: %s", budget, exc
        )
        fallback_result = _fallback(results, budget)
        if audit_mode:
            return fallback_result, {"method": "answer_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
        return fallback_result

    # --- Fetch stored chunk vectors from LanceDB -------------------------
    chunk_ids = [r.chunk_id for r in results]
    try:
        vec_map = _fetch_chunk_embeddings(chunk_ids, lancedb_path=lancedb_path)
    except Exception as exc:
        logger.warning(
            "LanceDB vector fetch failed, returning top-%d by RRF score: %s", budget, exc
        )
        fallback_result = _fallback(results, budget)
        if audit_mode:
            return fallback_result, {"method": "answer_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
        return fallback_result

    # --- Compute cosine similarity and sort ------------------------------
    result_map = {r.chunk_id: r for r in results}
    scored: list[tuple[str, float]] = []
    for chunk_id in result_map:
        if chunk_id in vec_map:
            similarity = float(np.dot(answer_vec, vec_map[chunk_id]))
        else:
            # Chunk has no stored embedding (e.g. cache-only chunk)
            similarity = 0.0
        scored.append((chunk_id, similarity))

    scored.sort(key=lambda x: -x[1])

    # --- Build output RetrievalResult list with updated scores -----------
    reranked: list[RetrievalResult] = []
    for chunk_id, similarity in scored[:budget]:
        r = result_map[chunk_id]
        reranked.append(
            RetrievalResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=round(max(similarity, 0.0), 4),
                citation=r.citation,
                section_title=r.section_title,
                agency=r.agency,
                authority_level=r.authority_level,
                document_type=r.document_type,
                retrieval_sources=r.retrieval_sources,
                graph_context=r.graph_context,
                citation_path=r.citation_path,
            )
        )

    logger.info(
        "Reranked %d chunks -> top %d for level %s (budget %d)",
        len(results), len(reranked), level, budget,
    )

    if audit_mode:
        # Build audit data
        before_map = {cid: (cit, sc) for cid, cit, sc in before_order}
        after_set = {r.chunk_id for r in reranked}
        dropped = [(cid, cit, sc) for cid, cit, sc in before_order if cid not in after_set]

        before_rank = {cid: idx for idx, (cid, _, _) in enumerate(before_order)}
        kept = []
        for idx, r in enumerate(reranked):
            old_rank = before_rank.get(r.chunk_id, len(before_order))
            kept.append({
                "citation": r.citation,
                "before_score": round(before_map.get(r.chunk_id, ("", 0))[1], 4),
                "after_score": round(r.score, 4),
                "rank_change": old_rank - idx,
            })

        audit_data = {
            "method": "answer_embedding",
            "before_count": len(results),
            "after_count": len(reranked),
            "kept": kept,
            "dropped": [{"citation": cit, "before_score": round(sc, 4)} for _, cit, sc in sorted(dropped, key=lambda x: -x[2])],
            "dropped_total": len(dropped),
        }
        return reranked, audit_data

    return reranked


def rerank_by_query(
    query: str,
    results: list[RetrievalResult],
    level: str,
    lancedb_path: Path | None = None,
    audit_mode: bool = False,
) -> list[RetrievalResult] | tuple[list[RetrievalResult], dict]:
    """Rerank chunks by cosine similarity to the query embedding (L1/L2).

    Mirrors rerank_by_answer but uses the query embedding instead of an answer
    embedding. Runs before synthesis — there is no LLM answer yet. Gives L1/L2
    queries the same second-pass scoring that L3+ gets via rerank_by_answer.

    Args:
        query: The user's query string.
        results: RetrievalResult objects from retrieve() + session cache merge.
        level: Query complexity level (L1-L6) for budget lookup.
        lancedb_path: Override LanceDB path (for testing).
        audit_mode: If True, return tuple of (reranked_results, audit_data).

    Returns:
        Reranked list of RetrievalResult, capped at SYNTHESIS_TOP_K[level].
        Scores updated to cosine similarity (0.0–1.0 scale).
        Falls back to top-budget by original fusion score on any failure.
        If audit_mode=True, returns (reranked_list, audit_data_dict).
    """
    budget = SYNTHESIS_TOP_K.get(level, RETRIEVAL_TOP_K)

    if not results:
        if audit_mode:
            return results, {"method": "query_embedding", "before_count": 0, "after_count": 0, "kept": [], "dropped": [], "dropped_total": 0}
        return results

    # --- Capture before state for audit --------------------------------
    before_order: list[tuple[str, str, float]] = [
        (r.chunk_id, r.citation, r.score) for r in results
    ]

    # --- Embed the query --------------------------------------------------
    try:
        raw_vec = embed_texts_sync([query[:8000]])[0]
        query_vec = np.array(raw_vec, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm == 0:
            logger.warning("Query embedding is zero vector, falling back to score ranking")
            fallback_result = _fallback(results, budget)
            if audit_mode:
                return fallback_result, {"method": "query_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
            return fallback_result
        query_vec = query_vec / norm
    except Exception as exc:
        logger.warning(
            "Query embedding failed, returning top-%d by score: %s", budget, exc
        )
        fallback_result = _fallback(results, budget)
        if audit_mode:
            return fallback_result, {"method": "query_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
        return fallback_result

    # --- Fetch stored chunk vectors from LanceDB -------------------------
    chunk_ids = [r.chunk_id for r in results]
    try:
        vec_map = _fetch_chunk_embeddings(chunk_ids, lancedb_path=lancedb_path)
    except Exception as exc:
        logger.warning(
            "LanceDB vector fetch failed, returning top-%d by score: %s", budget, exc
        )
        fallback_result = _fallback(results, budget)
        if audit_mode:
            return fallback_result, {"method": "query_embedding", "before_count": len(results), "after_count": len(fallback_result), "kept": [], "dropped": [], "dropped_total": 0, "fallback": True}
        return fallback_result

    # --- Compute cosine similarity and sort ------------------------------
    result_map = {r.chunk_id: r for r in results}
    scored: list[tuple[str, float]] = []
    for chunk_id in result_map:
        if chunk_id in vec_map:
            similarity = float(np.dot(query_vec, vec_map[chunk_id]))
        else:
            similarity = 0.0
        scored.append((chunk_id, similarity))

    scored.sort(key=lambda x: -x[1])

    # --- Build output RetrievalResult list with updated scores -----------
    reranked: list[RetrievalResult] = []
    for chunk_id, similarity in scored[:budget]:
        r = result_map[chunk_id]
        reranked.append(
            RetrievalResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=round(max(similarity, 0.0), 4),
                citation=r.citation,
                section_title=r.section_title,
                agency=r.agency,
                authority_level=r.authority_level,
                document_type=r.document_type,
                retrieval_sources=r.retrieval_sources,
                graph_context=r.graph_context,
                citation_path=r.citation_path,
            )
        )

    logger.info(
        "Query reranked %d chunks -> top %d for level %s (budget %d)",
        len(results), len(reranked), level, budget,
    )

    if audit_mode:
        # Build audit data
        before_map = {cid: (cit, sc) for cid, cit, sc in before_order}
        after_set = {r.chunk_id for r in reranked}
        dropped = [(cid, cit, sc) for cid, cit, sc in before_order if cid not in after_set]

        before_rank = {cid: idx for idx, (cid, _, _) in enumerate(before_order)}
        kept = []
        for idx, r in enumerate(reranked):
            old_rank = before_rank.get(r.chunk_id, len(before_order))
            kept.append({
                "citation": r.citation,
                "before_score": round(before_map.get(r.chunk_id, ("", 0))[1], 4),
                "after_score": round(r.score, 4),
                "rank_change": old_rank - idx,
            })

        audit_data = {
            "method": "query_embedding",
            "before_count": len(results),
            "after_count": len(reranked),
            "kept": kept,
            "dropped": [{"citation": cit, "before_score": round(sc, 4)} for _, cit, sc in sorted(dropped, key=lambda x: -x[2])],
            "dropped_total": len(dropped),
        }
        return reranked, audit_data

    return reranked


def _fallback(results: list[RetrievalResult], budget: int) -> list[RetrievalResult]:
    """Return top-budget results sorted by original fusion score (fallback)."""
    return sorted(results, key=lambda r: -r.score)[:budget]
