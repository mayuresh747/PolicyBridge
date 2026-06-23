"""Post-reranking graph expansion for authority chain injection.

After rerank_by_answer() selects top-k chunks by cosine similarity, this module
walks the Kuzu knowledge graph from the top-GRAPH_EXPAND_SEEDS chunks to find
additional authority chunks referenced via semantic edges (IMPLEMENTS, SUBJECT_TO,
DEFINED_BY, AMENDED_BY, CITES) and adjacent sequential chunks (NEXT_SECTION).

Scoring:
  - Semantic edges: combined = cosine_similarity(answer_vec, neighbor_vec)
                               x transition_weight[edge_type]
  - NEXT_SECTION: cosine_similarity only, with contiguity rule (no skipping)

Research basis: HippoRAG PPR (NeurIPS 2024), GAAMA edge weights (2025),
ToG-2 hub dampening (ICLR 2024).
"""

from __future__ import annotations

import logging
from pathlib import Path

import lancedb
import numpy as np

from src.config import (
    GRAPH_EXPAND_MAX_ADDITIONS,
    GRAPH_EXPAND_MAX_ADDITIONS_L12,
    GRAPH_EXPAND_MAX_HOPS,
    GRAPH_EXPAND_MAX_NEIGHBORS,
    GRAPH_EXPAND_NEXT_THRESHOLD,
    GRAPH_EXPAND_SEEDS,
    GRAPH_EXPAND_WEIGHTS,
    GRAPH_FEATURE_NEXT_ADAPTIVE,
    KUZU_PATH,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
)
from src.embeddings.openai_embedder import embed_texts_sync
from src.graph.kuzu_writer import KuzuWriter
from src.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


def expand_by_graph(
    top_results: list[RetrievalResult],
    tree_answer: str,
    lancedb_path: Path | None = None,
    kuzu_path: Path | None = None,
    max_additions: int | None = None,
    audit_mode: bool = False,
    override_seeds: list[str] | None = None,
    override_query_vec: np.ndarray | None = None,
) -> list[RetrievalResult] | tuple[list[RetrievalResult], dict]:
    """Expand synthesis context with graph-connected authority chunks.

    Takes the top GRAPH_EXPAND_SEEDS cosine-reranked chunks as expansion seeds.
    Walks semantic edges (1 hop, scored by cosine x transition_weight) and
    NEXT_SECTION chains (contiguous expansion, stops below threshold).
    Injects up to ``max_additions`` new chunks not already in top_results.

    Falls back silently to returning top_results unchanged on any error.

    Args:
        top_results: Cosine-reranked chunks (output of rerank_by_answer or
            rerank_by_query).
        tree_answer: Answer or query text used as the embedding for cosine
            scoring. For L3+ this is the tree answer; for L1/L2 it is the
            query string (via expand_by_graph_from_query).
        lancedb_path: Override LanceDB path (for testing).
        kuzu_path: Override Kuzu path (for testing).
        max_additions: Cap on how many new chunks to inject. Defaults to
            ``GRAPH_EXPAND_MAX_ADDITIONS`` (10). Pass a smaller value (e.g. 5)
            for L1/L2 queries via expand_by_graph_from_query.
        audit_mode: If True, return tuple of (results, audit_data).

    Returns:
        top_results + up to max_additions graph-expanded RetrievalResult
        objects (retrieval_sources=["graph_expand"]).
        If audit_mode=True, returns (results_list, audit_data_dict).
    """
    _max_additions = max_additions if max_additions is not None else GRAPH_EXPAND_MAX_ADDITIONS
    if not top_results:
        if audit_mode:
            return top_results, {"seeds_used": 0, "total_candidates": 0, "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    _kuzu_path = Path(kuzu_path) if kuzu_path else KUZU_PATH
    _lancedb_path = Path(lancedb_path) if lancedb_path else LANCEDB_PATH

    if not _kuzu_path.exists():
        logger.debug("Kuzu not found at %s — skipping graph expansion", _kuzu_path)
        return top_results

    # --- Resolve scoring vector ----------------------------------------
    # Phase 8 (08-04): when override_query_vec is supplied (S3 seed fusion
    # composite vector), reuse it and SKIP the answer embedding call —
    # D-06 binding: no new embed at this layer when a cached vector is
    # already available.
    if override_query_vec is not None:
        answer_vec = np.asarray(override_query_vec, dtype=np.float32)
        norm = float(np.linalg.norm(answer_vec))
        if norm == 0.0:
            return top_results
        if abs(norm - 1.0) > 1e-4:
            answer_vec = answer_vec / norm
    else:
        try:
            raw_vec = embed_texts_sync([tree_answer[:8000]])[0]
            answer_vec = np.array(raw_vec, dtype=np.float32)
            norm = np.linalg.norm(answer_vec)
            if norm == 0:
                return top_results
            answer_vec = answer_vec / norm
        except Exception as exc:
            logger.warning("Graph expansion: answer embedding failed: %s", exc)
            return top_results

    # --- Seeds and existing ID set -------------------------------------
    # S3 seed fusion supplies an explicit seed list that supersedes the
    # top_results[:N] slice.  Fall back to the legacy behaviour when no
    # override is given.
    if override_seeds:
        seed_ids = list(dict.fromkeys(override_seeds))[:GRAPH_EXPAND_SEEDS]
        # Keep `seeds` list aligned with seed_ids for audit emit below.
        seed_id_to_result = {r.chunk_id: r for r in top_results}
        seeds = [seed_id_to_result[sid] for sid in seed_ids if sid in seed_id_to_result]
    else:
        seeds = top_results[:GRAPH_EXPAND_SEEDS]
        seed_ids = [r.chunk_id for r in seeds]
    existing_ids = {r.chunk_id for r in top_results}

    # --- Query Kuzu ----------------------------------------------------
    semantic_candidates: dict[str, tuple[str, str]] = {}
    next_chains: dict[str, dict[str, list[str]]] = {
        sid: {"fwd": [], "bwd": []} for sid in seed_ids
    }

    try:
        with KuzuWriter(_kuzu_path) as writer:
            ids_str = ", ".join(f"'{cid}'" for cid in seed_ids)

            # Semantic edges: 1-hop outgoing, one query per edge type
            for edge_type, weight in GRAPH_EXPAND_WEIGHTS.items():
                try:
                    rows = writer.query(
                        f"MATCH (s:Chunk)-[r:{edge_type}]->(n:Chunk) "
                        f"WHERE s.id IN [{ids_str}] "
                        f"RETURN s.id, n.id"
                    )
                except Exception as exc:
                    logger.debug("Kuzu %s query failed: %s", edge_type, exc)
                    rows = []

                # Apply hub dampening: max GRAPH_EXPAND_MAX_NEIGHBORS per seed
                seed_count: dict[str, int] = {}
                for row in rows:
                    seed_id, neighbor_id = str(row[0]), str(row[1])
                    if neighbor_id in existing_ids:
                        continue
                    seed_count[seed_id] = seed_count.get(seed_id, 0) + 1
                    if seed_count[seed_id] > GRAPH_EXPAND_MAX_NEIGHBORS:
                        continue
                    existing_weight = GRAPH_EXPAND_WEIGHTS.get(
                        semantic_candidates.get(neighbor_id, (edge_type,))[0], 0
                    )
                    if neighbor_id not in semantic_candidates or weight > existing_weight:
                        semantic_candidates[neighbor_id] = (edge_type, seed_id)

            # NEXT_SECTION chains: per-seed, per-hop, per-direction
            for seed_id in seed_ids:
                # Forward: seed -> next -> next_next ...
                current = seed_id
                for _ in range(GRAPH_EXPAND_MAX_HOPS):
                    try:
                        rows = writer.query(
                            "MATCH (s:Chunk)-[:NEXT_SECTION]->(n:Chunk) "
                            "WHERE s.id = $id RETURN n.id",
                            {"id": current},
                        )
                    except Exception:
                        break
                    if not rows:
                        break
                    next_id = str(rows[0][0])
                    next_chains[seed_id]["fwd"].append(next_id)
                    current = next_id

                # Backward: prev -> seed
                current = seed_id
                for _ in range(GRAPH_EXPAND_MAX_HOPS):
                    try:
                        rows = writer.query(
                            "MATCH (n:Chunk)-[:NEXT_SECTION]->(s:Chunk) "
                            "WHERE s.id = $id RETURN n.id",
                            {"id": current},
                        )
                    except Exception:
                        break
                    if not rows:
                        break
                    prev_id = str(rows[0][0])
                    next_chains[seed_id]["bwd"].append(prev_id)
                    current = prev_id

    except Exception as exc:
        logger.warning("Kuzu graph expansion failed: %s", exc)
        if audit_mode:
            return top_results, {"seeds_used": 0, "total_candidates": 0, "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    # --- Collect all candidate chunk_ids for embedding fetch -----------
    all_candidate_ids: list[str] = []
    seen: set[str] = set()

    for cid in semantic_candidates:
        if cid not in seen:
            all_candidate_ids.append(cid)
            seen.add(cid)

    for seed_id, dirs in next_chains.items():
        for chain in dirs.values():
            for cid in chain:
                if cid not in seen and cid not in existing_ids:
                    all_candidate_ids.append(cid)
                    seen.add(cid)

    if not all_candidate_ids:
        if audit_mode:
            return top_results, {"seeds_used": len(seeds), "total_candidates": 0, "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    # --- Batch-fetch embeddings from LanceDB ---------------------------
    # Phase 8 S7 (08-05): when GRAPH_FEATURE_NEXT_ADAPTIVE is on, also pull
    # document_type for each candidate so the NEXT_SECTION threshold check
    # below can consult the per-doctype table. Flag off -> legacy select
    # shape (no schema change).
    _select_cols = ["id", "embedding"]
    if GRAPH_FEATURE_NEXT_ADAPTIVE:
        _select_cols.append("document_type")
    try:
        db = lancedb.connect(str(_lancedb_path))
        table = db.open_table(LANCEDB_TABLE_NAME)
        ids_sql = ", ".join(f"'{cid}'" for cid in all_candidate_ids)
        vec_df = (
            table.search()
            .where(f"id IN ({ids_sql})")
            .limit(len(all_candidate_ids))
            .select(_select_cols)
            .to_pandas()
        )
    except Exception as exc:
        logger.warning("Graph expansion: LanceDB embedding fetch failed: %s", exc)
        if audit_mode:
            return top_results, {"seeds_used": len(seeds), "total_candidates": 0, "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    # --- Build normalised embedding map --------------------------------
    vec_map: dict[str, np.ndarray] = {}
    doctype_map: dict[str, str] = {}
    for _, row in vec_df.iterrows():
        v = np.array(row["embedding"], dtype=np.float32)
        v_norm = np.linalg.norm(v)
        if v_norm > 0:
            vec_map[str(row["id"])] = v / v_norm
        if GRAPH_FEATURE_NEXT_ADAPTIVE:
            dt = row.get("document_type", "") if hasattr(row, "get") else ""
            doctype_map[str(row["id"])] = str(dt or "")

    # --- Score semantic candidates -------------------------------------
    scored: list[tuple[str, float, str, str]] = []
    added_ids: set[str] = set()

    for neighbor_id, (edge_type, seed_id) in semantic_candidates.items():
        if neighbor_id not in vec_map:
            continue
        cosine = float(np.dot(answer_vec, vec_map[neighbor_id]))
        weight = GRAPH_EXPAND_WEIGHTS[edge_type]
        combined = cosine * weight
        if neighbor_id not in added_ids:
            scored.append((neighbor_id, combined, edge_type, seed_id))
            added_ids.add(neighbor_id)

    # --- Score NEXT_SECTION candidates with contiguity rule -----------
    # Phase 8 S7 (08-05): per-document-type threshold lookup behind
    # GRAPH_FEATURE_NEXT_ADAPTIVE. Flag off preserves legacy single
    # GRAPH_EXPAND_NEXT_THRESHOLD byte-for-byte.
    if GRAPH_FEATURE_NEXT_ADAPTIVE:
        from src.graph.next_chain_policy import threshold_for
    for seed_id, dirs in next_chains.items():
        for direction, chain in dirs.items():
            for chunk_id in chain:
                if chunk_id in existing_ids:
                    continue
                if chunk_id not in vec_map:
                    break
                cosine = float(np.dot(answer_vec, vec_map[chunk_id]))
                if GRAPH_FEATURE_NEXT_ADAPTIVE:
                    doc_type = doctype_map.get(chunk_id, "")
                    thresh = threshold_for(doc_type)
                else:
                    thresh = GRAPH_EXPAND_NEXT_THRESHOLD
                if cosine < thresh:
                    break
                if chunk_id not in added_ids:
                    scored.append((chunk_id, cosine, "NEXT_SECTION", seed_id))
                    added_ids.add(chunk_id)

    if not scored:
        if audit_mode:
            return top_results, {"seeds_used": len(seeds), "total_candidates": len(all_candidate_ids), "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    # --- Sort by combined score, take top budget ----------------------
    scored.sort(key=lambda x: -x[1])
    winners = scored[:_max_additions]
    winner_ids = [w[0] for w in winners]

    # --- Batch-fetch full text + metadata for winners from LanceDB ---
    try:
        win_ids_sql = ", ".join(f"'{cid}'" for cid in winner_ids)
        meta_df = (
            table.search()
            .where(f"id IN ({win_ids_sql})")
            .limit(len(winner_ids))
            .to_pandas()
        )
        meta_map: dict[str, dict] = {}
        for _, row in meta_df.iterrows():
            meta_map[str(row["id"])] = row.to_dict()
    except Exception as exc:
        logger.warning("Graph expansion: LanceDB metadata fetch failed: %s", exc)
        if audit_mode:
            return top_results, {"seeds_used": len(seeds), "total_candidates": len(scored), "added": [], "skipped_already_present": 0, "additions_count": 0}
        return top_results

    # --- Build RetrievalResult objects for graph additions ------------
    graph_additions: list[RetrievalResult] = []
    score_map = {cid: (score, etype, sid) for cid, score, etype, sid in winners}

    for chunk_id in winner_ids:
        row = meta_map.get(chunk_id)
        if row is None:
            continue
        score, edge_type, seed_id = score_map[chunk_id]
        graph_additions.append(
            RetrievalResult(
                chunk_id=chunk_id,
                text=str(row.get("text", "")),
                score=round(max(score, 0.0), 4),
                citation=str(row.get("citation", "")),
                section_title=row.get("section_title"),
                agency=str(row.get("agency", "")),
                authority_level=str(row.get("authority_level", "")),
                document_type=str(row.get("document_type", "")),
                retrieval_sources=["graph_expand"],
                graph_context=[{"rel_type": edge_type, "seed_chunk_id": seed_id}],
                citation_path={},
            )
        )

    if graph_additions:
        logger.info(
            "Graph expansion: %d seeds -> %d additions (from %d candidates)",
            len(seeds), len(graph_additions), len(scored),
        )

    if audit_mode:
        # Build audit data: create added list with seed citations
        seed_map = {r.chunk_id: r.citation for r in seeds}
        added = []
        for idx, r in enumerate(graph_additions):
            edge_type = "unknown"
            seed_id = ""
            if r.graph_context:
                ctx = r.graph_context[0] if r.graph_context else {}
                edge_type = ctx.get("rel_type", "unknown")
                seed_id = ctx.get("seed_chunk_id", "")
            seed_citation = seed_map.get(seed_id, "")
            added.append({
                "chunk_id": r.chunk_id,
                "citation": r.citation,
                "seed_citation": seed_citation,
                "edge_type": edge_type,
                "score": round(r.score, 4),
            })

        audit_data = {
            "seeds_used": len(seeds),
            "total_candidates": len(scored),
            "added": added,
            "skipped_already_present": 0,
            "additions_count": len(graph_additions),
        }
        return top_results + graph_additions, audit_data

    return top_results + graph_additions


def expand_by_graph_from_query(
    top_results: list[RetrievalResult],
    query: str,
    lancedb_path: Path | None = None,
    kuzu_path: Path | None = None,
    audit_mode: bool = False,
) -> list[RetrievalResult] | tuple[list[RetrievalResult], dict]:
    """L1/L2 graph expansion: use query embedding as the scoring vector.

    Thin wrapper around expand_by_graph that passes the query string instead
    of a tree_answer, and uses a smaller max_additions budget (5 vs 10 for
    L3+). Intended to be called after rerank_by_query in the L1/L2 pipeline
    branch, mirroring the L3+ pattern of expand_by_graph after rerank_by_answer.

    Args:
        top_results: Cosine-reranked chunks (output of rerank_by_query).
        query: The user's query string, used as the embedding reference for
            scoring graph-traversed neighbors.
        lancedb_path: Override LanceDB path (for testing).
        kuzu_path: Override Kuzu path (for testing).
        audit_mode: If True, return tuple of (results, audit_data).

    Returns:
        top_results + up to GRAPH_EXPAND_MAX_ADDITIONS_L12 graph-expanded
        RetrievalResult objects (retrieval_sources=["graph_expand"]).
        If audit_mode=True, returns (results_list, audit_data_dict).
    """
    return expand_by_graph(
        top_results,
        query,
        lancedb_path=lancedb_path,
        kuzu_path=kuzu_path,
        max_additions=GRAPH_EXPAND_MAX_ADDITIONS_L12,
        audit_mode=audit_mode,
    )
