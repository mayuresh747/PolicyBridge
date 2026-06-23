"""Fusion functions for combining ranked retrieval lists.

Two strategies are provided:

``rrf_fuse`` — Reciprocal Rank Fusion (legacy, kept for reference/tests):
    RRF_score(chunk) = sum(weight_s / (k + rank_s)) for each source s

``linear_fuse`` — Min-max normalized linear fusion (active):
    Each source's raw scores are independently normalized to [0, 1], then
    weighted-summed. Chunks absent from a source receive 0.0 for that source.
    Because scores are commensurable after normalization, weights behave as
    intended: a weight-0.45 BM25 rank-1 chunk can beat a weight-0.55 vector
    chunk that is not near the top of its list. With RRF and k=60 this is
    structurally impossible.
"""

from collections import defaultdict

from src.config import RRF_K


def rrf_fuse(
    ranked_lists: dict[str, list[str]],
    weights: dict[str, float] | None = None,
    k: int = RRF_K,
) -> list[tuple[str, float, list[str]]]:
    """Combine ranked lists using weighted Reciprocal Rank Fusion.

    Per D-01: ``RRF_score = sum(weight / (k + rank))`` across all lists.
    Rank is 1-indexed (per pitfall #3: ``enumerate`` is 0-indexed, so we
    use ``rank_0 + 1``).

    Args:
        ranked_lists: Dict mapping source name (e.g., "vector", "bm25",
            "graph") to an ordered list of chunk IDs (best first).
        weights: Dict mapping source name to its weight.  Defaults to
            equal weights of 1.0 for all sources.
        k: RRF constant (default 60).  Higher k reduces the influence
            of top-ranked results relative to lower-ranked ones.

    Returns:
        List of ``(chunk_id, fused_score, sources)`` tuples sorted
        descending by ``fused_score``.  ``sources`` is the list of source
        names where the chunk appeared.
    """
    if weights is None:
        weights = {name: 1.0 for name in ranked_lists}

    scores: dict[str, float] = defaultdict(float)
    sources: dict[str, list[str]] = defaultdict(list)

    for source_name, chunk_ids in ranked_lists.items():
        weight = weights.get(source_name, 0.0)
        for rank_0, chunk_id in enumerate(chunk_ids):
            scores[chunk_id] += weight / (k + rank_0 + 1)  # 1-indexed rank
            if source_name not in sources[chunk_id]:
                sources[chunk_id].append(source_name)

    sorted_results = sorted(scores.items(), key=lambda x: -x[1])
    return [(cid, score, sources[cid]) for cid, score in sorted_results]


def linear_fuse(
    ranked_lists: dict[str, list[tuple[str, float]]],
    weights: dict[str, float] | None = None,
) -> list[tuple[str, float, list[str]]]:
    """Combine ranked lists using min-max normalized linear fusion.

    Each source's raw scores are independently min-max normalized to [0, 1],
    then weighted-summed. Chunks absent from a source receive 0.0 for that
    source (floor, not penalty). Because scores are commensurable after
    normalization, weights behave as intended: a BM25 rank-1 chunk can
    outrank a vector chunk that sits near the bottom of the vector list.

    Edge cases:
    - Empty source list: contributes nothing to any chunk's fused score.
    - Singleton or all-equal-score list: all chunks get normalized score 1.0.

    Args:
        ranked_lists: Dict mapping source name (e.g., ``"vector"``, ``"bm25"``)
            to an ordered list of ``(chunk_id, raw_score)`` tuples. Higher
            raw_score means more relevant. The order within each list is used
            only to collect chunk IDs; normalization is score-based, not rank-based.
        weights: Dict mapping source name to weight. Defaults to equal weights
            of 1.0 for all sources.

    Returns:
        List of ``(chunk_id, fused_score, sources)`` tuples sorted descending
        by ``fused_score``. ``sources`` lists the source names that contributed
        to each chunk (i.e., where the chunk appeared).
    """
    if weights is None:
        weights = {name: 1.0 for name in ranked_lists}

    # Normalize each source's scores independently to [0, 1] via min-max
    norm_scores: dict[str, dict[str, float]] = {}
    for source_name, id_score_pairs in ranked_lists.items():
        if not id_score_pairs:
            norm_scores[source_name] = {}
            continue
        raw = [s for _, s in id_score_pairs]
        lo, hi = min(raw), max(raw)
        span = hi - lo
        if span == 0:
            # Singleton or all-equal: assign 1.0 to every chunk in this list
            norm_scores[source_name] = {cid: 1.0 for cid, _ in id_score_pairs}
        else:
            norm_scores[source_name] = {
                cid: (score - lo) / span for cid, score in id_score_pairs
            }

    # Collect all chunk IDs in insertion order (dedup across sources)
    all_ids: list[str] = []
    seen: set[str] = set()
    for id_score_pairs in ranked_lists.values():
        for cid, _ in id_score_pairs:
            if cid not in seen:
                all_ids.append(cid)
                seen.add(cid)

    # Weighted sum of normalized scores
    fused_scores: dict[str, float] = {}
    chunk_sources: dict[str, list[str]] = {}
    for cid in all_ids:
        total = 0.0
        sources_for_chunk: list[str] = []
        for source_name, ns_dict in norm_scores.items():
            if cid in ns_dict:
                total += weights.get(source_name, 0.0) * ns_dict[cid]
                sources_for_chunk.append(source_name)
        fused_scores[cid] = total
        chunk_sources[cid] = sources_for_chunk

    sorted_results = sorted(fused_scores.items(), key=lambda x: -x[1])
    return [(cid, score, chunk_sources[cid]) for cid, score in sorted_results]
