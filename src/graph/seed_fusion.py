"""S3: multi-sub-question seed fusion (for L3+ queries).

On L3+ queries the pipeline decomposes into sub-questions; each produces its
own ranked retrieval AND its own query embedding. Instead of running N tiny
per-leaf expansions, this module unions the top seeds across sub-questions
into a single ordered list and builds a composite vector (L2-normalised
mean of the per-sub-question embeddings) that downstream beam / graph
expansion can score against.

Binding constraint (Phase 8 D-01 / D-06):
    **Zero new API / LLM / embedding calls.**

    Both the seeds and the embeddings must already be computed upstream:
    - ``seed_chunk_ids`` come from the per-leaf ``retrieve()`` result.
    - ``query_vec`` comes from ``retrieve(..., return_query_vec=True)`` —
      ``vector_search`` already computes it; we just bubble it out.

    If a given leaf has ``query_vec=None`` (e.g., retrieve() fell back with
    no vector produced) we SKIP it from the composite-vector average. We
    NEVER embed as a fallback here. Callers that need a vector and get
    ``None`` back must fall back cleanly (e.g., use the answer-embedding
    path in graph_expander.py).

Module boundary:
    - No imports from ``src.embeddings``, ``src.query``, ``src.retrieval``.
    - No Kuzu / LanceDB access.
    - Pure function: given ``list[SubQuestionResult]``, return ``(seed_ids,
      composite_vec)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SubQuestionResult:
    """Per-leaf payload the fuser consumes.

    Constructed by the caller (``pipeline.py``) from the decomposer tree;
    this module does NOT inspect TreeNode internals.

    Attributes:
        sub_question: The leaf's sub-question text. Informational only —
            fuse_seeds does not read it, but keeping it on the dataclass
            makes debugging / audit logging trivial for callers.
        seed_chunk_ids: Ranked (best first) list of chunk ids produced by
            the per-leaf ``retrieve()`` call. Typically the caller will
            pre-slice to the top-N it wants to contribute.
        query_vec: L2-normalised ``np.float32`` embedding of ``sub_question``,
            cached by ``retrieve()``. ``None`` if no embedding is available
            — the leaf is then skipped from the composite-vector average
            (never re-embedded).
    """

    sub_question: str
    seed_chunk_ids: list[str]
    query_vec: np.ndarray | None


def fuse_seeds(
    sub_question_results: list[SubQuestionResult],
    per_seed_top_n: int = 3,
) -> tuple[list[str], np.ndarray | None]:
    """Union per-leaf seeds and average per-leaf embeddings into a composite.

    Ordering: seeds appear in the order (sub_question_index, rank). A chunk
    id that appears in multiple leaves keeps only its first occurrence
    (earliest sub-question, then earliest rank) — subsequent duplicates
    are dropped.

    Composite vector: L2-normalised arithmetic mean of the non-None
    ``query_vec`` attributes. If every leaf has ``query_vec=None`` the
    composite is ``None`` and callers must fall back cleanly — fuse_seeds
    never computes a new embedding.

    Args:
        sub_question_results: List of per-leaf payloads. Empty list returns
            ``([], None)``.
        per_seed_top_n: Per-leaf cap on how many seed ids to contribute to
            the union. Keeps the fused seed set bounded so the downstream
            beam stays small.

    Returns:
        Tuple ``(seed_ids, composite_vec)`` where ``seed_ids`` is a
        deduplicated list of chunk ids (possibly empty) and ``composite_vec``
        is either a unit-length ``np.ndarray`` with shape matching the input
        embeddings, or ``None`` if no usable embedding was available.
    """
    if not sub_question_results:
        return [], None

    # --- Seed union (order-preserving dedup) --------------------------------
    seen: set[str] = set()
    seed_ids: list[str] = []
    for sub in sub_question_results:
        for cid in sub.seed_chunk_ids[:per_seed_top_n]:
            if cid in seen:
                continue
            seen.add(cid)
            seed_ids.append(cid)

    # --- Composite vector (mean of non-None query_vec) ---------------------
    vectors = [
        sub.query_vec
        for sub in sub_question_results
        if sub.query_vec is not None
    ]

    if not vectors:
        return seed_ids, None

    stacked = np.stack(vectors, axis=0).astype(np.float32, copy=False)
    mean = stacked.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm == 0.0:
        # Degenerate case — cancellation produced a zero vector. Do NOT try
        # to recover by embedding; return None and let the caller fall back.
        return seed_ids, None

    composite_vec = mean / norm
    return seed_ids, composite_vec.astype(np.float32, copy=False)
