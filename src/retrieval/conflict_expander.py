"""Runtime conflict expansion for conflict-seeking queries.

Two approaches combined into a single ``expand_conflicts()`` entry point:

Approach 1 — Shared-authority graph proxy (zero cost):
    For each seed chunk, query Kuzu for other chunks that IMPLEMENTS the same
    target (e.g., same RCW) from a *different* agency.  Two agencies implementing
    the same statute is the primary source of regulatory conflict.

Approach 2 — Cross-agency vector search (cheap):
    For each seed chunk, run a LanceDB vector search filtered to OTHER agencies.
    Finds same-topic chunks from different authority levels that may contain
    conflicting or constraining requirements.

Both approaches skip chunks already present in the result set and score
candidates by cosine similarity to the query/answer embedding so only
topically relevant conflicts are injected.
"""

from __future__ import annotations

import logging
from pathlib import Path

import lancedb
import numpy as np

from src.config import (
    CONFLICT_CROSS_AGENCY_PER_SEED,
    CONFLICT_CROSS_AGENCY_SEEDS,
    CONFLICT_CROSS_AGENCY_THRESHOLD,
    CONFLICT_EXPAND_ENABLED,
    CONFLICT_EXPAND_MAX,
    KUZU_PATH,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
    VALID_AGENCIES,
)
from src.embeddings.openai_embedder import embed_texts_sync
from src.graph.kuzu_writer import KuzuWriter
from src.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Approach 1: Shared-authority graph proxy
# ---------------------------------------------------------------------------


def _shared_authority_search(
    writer: KuzuWriter,
    seed_ids: list[str],
    existing_ids: set[str],
) -> list[dict]:
    """Find chunks from other agencies that IMPLEMENTS the same target.

    For each seed, queries:
        (seed)-[:IMPLEMENTS]->(target)<-[:IMPLEMENTS]-(other)
        WHERE other.agency != seed.agency

    Args:
        writer: Open KuzuWriter connection.
        seed_ids: Chunk IDs to use as expansion seeds.
        existing_ids: Chunk IDs already in results (skip these).

    Returns:
        List of dicts with keys: chunk_id, agency, citation,
        shared_target, seed_id, source_approach.
    """
    candidates: list[dict] = []
    seen: set[str] = set()

    for seed_id in seed_ids:
        try:
            rows = writer.query(
                "MATCH (seed:Chunk)-[:IMPLEMENTS]->(target:Chunk)"
                "<-[:IMPLEMENTS]-(other:Chunk) "
                "WHERE seed.id = $id AND other.agency <> seed.agency "
                "RETURN other.id, other.agency, other.citation, "
                "target.citation, seed.id",
                {"id": seed_id},
            )
        except Exception as exc:
            logger.debug(
                "Shared-authority query failed for seed %s: %s",
                seed_id, exc,
            )
            continue

        for row in rows:
            other_id = str(row[0])
            if other_id in existing_ids or other_id in seen:
                continue
            seen.add(other_id)
            candidates.append({
                "chunk_id": other_id,
                "agency": str(row[1]),
                "citation": str(row[2]),
                "shared_target": str(row[3]),
                "seed_id": str(row[4]),
                "source_approach": "shared_authority",
            })

    logger.info(
        "Shared-authority search: %d seeds -> %d candidates",
        len(seed_ids), len(candidates),
    )
    return candidates


# ---------------------------------------------------------------------------
# Approach 2: Cross-agency vector search
# ---------------------------------------------------------------------------


def _cross_agency_vector_search(
    table,
    seeds: list[RetrievalResult],
    existing_ids: set[str],
    per_seed: int = CONFLICT_CROSS_AGENCY_PER_SEED,
    threshold: float = CONFLICT_CROSS_AGENCY_THRESHOLD,
) -> list[dict]:
    """For each seed chunk, vector-search for same-topic chunks in other agencies.

    Uses the seed chunk's text (first 500 chars) as the search query with an
    agency exclusion filter.  Only keeps results above the cosine threshold.

    Args:
        table: Open LanceDB table.
        seeds: Top RetrievalResult objects used as search seeds.
        existing_ids: Chunk IDs already in results (skip these).
        per_seed: Max cross-agency results per seed.
        threshold: Minimum cosine similarity to keep a result.

    Returns:
        List of dicts with keys: chunk_id, agency, citation, seed_id,
        cosine, source_approach.
    """
    candidates: list[dict] = []
    seen: set[str] = set()

    for seed in seeds:
        # Validate agency for the WHERE clause (SQL injection prevention)
        if seed.agency not in VALID_AGENCIES:
            continue

        try:
            cross_df = (
                table.search(seed.text[:500])
                .where(f"agency != '{seed.agency}'")
                .limit(per_seed)
                .to_pandas()
            )
        except Exception as exc:
            logger.debug(
                "Cross-agency search failed for seed %s: %s",
                seed.chunk_id, exc,
            )
            continue

        if cross_df.empty:
            continue

        for _, row in cross_df.iterrows():
            chunk_id = str(row["id"])
            if chunk_id in existing_ids or chunk_id in seen:
                continue

            # LanceDB search returns _distance (cosine distance); convert
            distance = float(row.get("_distance", 1.0))
            cosine = 1.0 - distance
            if cosine < threshold:
                continue

            seen.add(chunk_id)
            candidates.append({
                "chunk_id": chunk_id,
                "agency": str(row.get("agency", "")),
                "citation": str(row.get("citation", "")),
                "seed_id": seed.chunk_id,
                "cosine": cosine,
                "source_approach": "cross_agency_vector",
            })

    logger.info(
        "Cross-agency vector search: %d seeds -> %d candidates",
        len(seeds), len(candidates),
    )
    return candidates


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def expand_conflicts(
    results: list[RetrievalResult],
    query_or_answer: str,
    lancedb_path: Path | None = None,
    kuzu_path: Path | None = None,
    max_additions: int = CONFLICT_EXPAND_MAX,
    audit_mode: bool = False,
) -> list[RetrievalResult] | tuple[list[RetrievalResult], dict]:
    """Expand results with potentially conflicting cross-agency chunks.

    Combines shared-authority graph proxy (Approach 1) and cross-agency
    vector search (Approach 2).  Scores all candidates by cosine similarity
    to ``query_or_answer`` and injects the top ``max_additions``.

    Falls back silently to returning results unchanged on any error.

    Args:
        results: Current RetrievalResult list (post-rerank + graph_expand).
        query_or_answer: Query string (L1/L2) or tree_answer (L3+), used
            to score candidate relevance.
        lancedb_path: Override LanceDB path (for testing).
        kuzu_path: Override Kuzu path (for testing).
        max_additions: Maximum conflict chunks to inject.
        audit_mode: If True, return tuple of (results, audit_data).

    Returns:
        results + up to max_additions conflict-expanded RetrievalResult
        objects (retrieval_sources=["conflict_expand"]).
        If audit_mode=True, returns (results_list, audit_data_dict).
    """
    if not CONFLICT_EXPAND_ENABLED or not results:
        if audit_mode:
            return results, {"conflict_seeking": True, "approach_1_hits": [], "approach_2_hits": [], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
        return results

    _kuzu_path = Path(kuzu_path) if kuzu_path else KUZU_PATH
    _lancedb_path = Path(lancedb_path) if lancedb_path else LANCEDB_PATH

    existing_ids = {r.chunk_id for r in results}

    # --- Seeds: use the top-scored chunks from current results ---------------
    seeds = sorted(results, key=lambda r: -r.score)[:CONFLICT_CROSS_AGENCY_SEEDS]
    seed_ids = [r.chunk_id for r in seeds]

    # --- Approach 1: Shared-authority graph proxy ----------------------------
    graph_candidates: list[dict] = []
    if _kuzu_path.exists():
        try:
            with KuzuWriter(_kuzu_path) as writer:
                graph_candidates = _shared_authority_search(
                    writer, seed_ids, existing_ids,
                )
        except Exception as exc:
            logger.warning("Conflict graph search failed: %s", exc)

    # --- Approach 2: Cross-agency vector search ------------------------------
    vector_candidates: list[dict] = []
    try:
        db = lancedb.connect(str(_lancedb_path))
        table = db.open_table(LANCEDB_TABLE_NAME)
        vector_candidates = _cross_agency_vector_search(
            table, seeds, existing_ids,
        )
    except Exception as exc:
        logger.warning("Conflict cross-agency search failed: %s", exc)

    # --- Merge and deduplicate candidates ------------------------------------
    all_candidates: dict[str, dict] = {}
    for c in graph_candidates + vector_candidates:
        cid = c["chunk_id"]
        if cid not in all_candidates:
            all_candidates[cid] = c
        else:
            # If found by both approaches, mark as stronger signal
            existing = all_candidates[cid]
            if existing["source_approach"] != c["source_approach"]:
                existing["source_approach"] = "shared_authority+cross_agency"

    if not all_candidates:
        logger.debug("Conflict expansion: no candidates found")
        if audit_mode:
            return results, {"conflict_seeking": True, "approach_1_hits": [], "approach_2_hits": [], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
        return results

    # --- Score candidates by cosine similarity to query/answer ---------------
    candidate_ids = list(all_candidates.keys())

    try:
        raw_vec = embed_texts_sync([query_or_answer[:8000]])[0]
        ref_vec = np.array(raw_vec, dtype=np.float32)
        norm = np.linalg.norm(ref_vec)
        if norm == 0:
            if audit_mode:
                return results, {"conflict_seeking": True, "approach_1_hits": [c for c in graph_candidates[:20]], "approach_2_hits": [c for c in vector_candidates[:20]], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
            return results
        ref_vec = ref_vec / norm
    except Exception as exc:
        logger.warning("Conflict expansion: embedding failed: %s", exc)
        if audit_mode:
            return results, {"conflict_seeking": True, "approach_1_hits": [c for c in graph_candidates[:20]], "approach_2_hits": [c for c in vector_candidates[:20]], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
        return results

    # Batch-fetch embeddings for candidates
    try:
        db = lancedb.connect(str(_lancedb_path))
        table = db.open_table(LANCEDB_TABLE_NAME)
        ids_sql = ", ".join(f"'{cid}'" for cid in candidate_ids)
        vec_df = (
            table.search()
            .where(f"id IN ({ids_sql})")
            .limit(len(candidate_ids))
            .select(["id", "embedding"])
            .to_pandas()
        )
    except Exception as exc:
        logger.warning("Conflict expansion: embedding fetch failed: %s", exc)
        if audit_mode:
            return results, {"conflict_seeking": True, "approach_1_hits": [c for c in graph_candidates[:20]], "approach_2_hits": [c for c in vector_candidates[:20]], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
        return results

    vec_map: dict[str, np.ndarray] = {}
    for _, row in vec_df.iterrows():
        v = np.array(row["embedding"], dtype=np.float32)
        v_norm = np.linalg.norm(v)
        if v_norm > 0:
            vec_map[str(row["id"])] = v / v_norm

    # Score and rank
    scored: list[tuple[str, float]] = []
    for cid in candidate_ids:
        if cid in vec_map:
            cosine = float(np.dot(ref_vec, vec_map[cid]))
            scored.append((cid, cosine))

    scored.sort(key=lambda x: -x[1])
    winners = scored[:max_additions]

    if not winners:
        return results

    # --- Fetch full metadata for winners -------------------------------------
    winner_ids = [w[0] for w in winners]
    try:
        win_sql = ", ".join(f"'{cid}'" for cid in winner_ids)
        meta_df = (
            table.search()
            .where(f"id IN ({win_sql})")
            .limit(len(winner_ids))
            .to_pandas()
        )
        meta_map: dict[str, dict] = {}
        for _, row in meta_df.iterrows():
            meta_map[str(row["id"])] = row.to_dict()
    except Exception as exc:
        logger.warning("Conflict expansion: metadata fetch failed: %s", exc)
        if audit_mode:
            return results, {"conflict_seeking": True, "approach_1_hits": [c for c in graph_candidates[:20]], "approach_2_hits": [c for c in vector_candidates[:20]], "added_count": 0, "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD}
        return results

    # --- Build RetrievalResult objects ---------------------------------------
    additions: list[RetrievalResult] = []
    score_map = {cid: score for cid, score in winners}

    for chunk_id in winner_ids:
        row = meta_map.get(chunk_id)
        if row is None:
            continue
        cand = all_candidates[chunk_id]
        score = score_map[chunk_id]

        # Build provenance context for the conflict tag
        provenance: dict = {
            "source_approach": cand["source_approach"],
            "seed_chunk_id": cand["seed_id"],
        }
        if "shared_target" in cand:
            provenance["shared_authority_target"] = cand["shared_target"]

        additions.append(
            RetrievalResult(
                chunk_id=chunk_id,
                text=str(row.get("text", "")),
                score=round(max(score, 0.0), 4),
                citation=str(row.get("citation", "")),
                section_title=row.get("section_title"),
                agency=str(row.get("agency", "")),
                authority_level=str(row.get("authority_level", "")),
                document_type=str(row.get("document_type", "")),
                retrieval_sources=["conflict_expand"],
                graph_context=[provenance],
                citation_path={},
            )
        )

    if additions:
        logger.info(
            "Conflict expansion: %d additions (from %d candidates, "
            "%d graph + %d vector)",
            len(additions), len(all_candidates),
            len(graph_candidates), len(vector_candidates),
        )

    if audit_mode:
        audit_data = {
            "conflict_seeking": True,
            "approach_1_hits": [
                {"chunk_id": c["chunk_id"], "citation": c["citation"], "agency": c["agency"],
                 "shared_target": c.get("shared_target", ""), "seed_id": c["seed_id"]}
                for c in graph_candidates
            ],
            "approach_2_hits": [
                {"chunk_id": c["chunk_id"], "citation": c["citation"], "agency": c["agency"],
                 "seed_id": c["seed_id"], "cosine": round(c.get("cosine", 0), 4)}
                for c in vector_candidates
            ],
            "added_count": len(additions),
            "threshold": CONFLICT_CROSS_AGENCY_THRESHOLD,
        }
        return results + additions, audit_data

    return results + additions
