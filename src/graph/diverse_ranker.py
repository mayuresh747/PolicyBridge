"""S5: MMR-style diversity ranker for graph traversal / retrieval output.

Selects ``k`` items maximising

    lambda_ * relevance  -  (1 - lambda_) * max_overlap_with_selected

where ``max_overlap_with_selected`` is ``1`` if the candidate shares its
diversity key with any already-selected item, else ``0``. The diversity
key is the tuple ``(filename_or_citation, section_number, agency)`` (D-07);
for candidates missing citation metadata the key falls back to
``(chunk_id, "", "")`` so distinct chunks remain distinguishable.

The default ``lambda_=0.7`` keeps relevance dominant but dampens hub-family
flooding — e.g., prevents the final top-k from being 10 siblings of a single
hub document.

Boundary: pure-Python greedy selection. No Kuzu, no LanceDB, no embedding
calls. Accepts any object with ``.chunk_id`` and ``.score`` (and optionally
``.citation`` / ``.agency`` / ``.section_title``).
"""

from __future__ import annotations

import re
from typing import Any

# Match trailing numeric / dotted section numbers in citations such as:
#     "SMC 23.44.014"         -> "23.44.014"
#     "RCW 36.70A.681"        -> "36.70A.681"
#     "WAC 51-50-000"         -> "51-50-000"
#     "DIR 5-2022 §3"         -> "3"   (best-effort)
# If no match, we fall back to the full citation string so each unique
# citation still dedupes against itself.
_SECTION_NUMBER_RE = re.compile(r"([0-9][0-9A-Za-z.\-]*)\s*$")


def _get(obj: Any, attr: str, default: str = "") -> str:
    """Defensive attribute/key access returning a string."""
    value = getattr(obj, attr, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(attr)
    if value is None:
        return default
    return str(value)


def _section_number(citation: str) -> str:
    """Extract a section-number token from a citation string.

    For citations like ``"SMC 23.44.014"`` returns ``"23.44.014"``.
    Falls back to the full citation if nothing matched (so dedup still
    works on the raw string).
    """
    if not citation:
        return ""
    m = _SECTION_NUMBER_RE.search(citation)
    return m.group(1) if m else citation


def _diversity_key(item: Any) -> tuple[str, str, str]:
    """Return ``(filename_or_citation_prefix, section_number, agency)``.

    Strategy:
        - If ``citation`` is available, use ``(citation, section_number, agency)``
          — this is the D-07 primary key.
        - If no citation (e.g., a bare ScoredPath from beam traversal), fall
          back to ``(chunk_id, "", "")`` so each distinct chunk is its own
          bucket and MMR degrades to pure relevance for that subset.
    """
    citation = _get(item, "citation", "")
    agency = _get(item, "agency", "")

    if citation:
        return (citation, _section_number(citation), agency)

    # No citation metadata — fall back to chunk_id so unique chunks keep
    # unique keys.  This preserves correctness on beam-layer candidates
    # where only .chunk_id and .score are guaranteed.
    chunk_id = _get(item, "chunk_id", "")
    return (chunk_id, "", agency)


def diverse_topk(
    scored_candidates: list,
    k: int,
    lambda_: float = 0.7,
) -> list:
    """Greedy MMR selection over ``scored_candidates``.

    Args:
        scored_candidates: Any iterable of objects with ``.score`` and a
            diversity key (preferably ``.citation`` + ``.agency``; otherwise
            ``.chunk_id``). Order is irrelevant — the function sorts.
        k: Number of items to return. If ``k >= len(scored_candidates)``
            all candidates are returned, re-ranked by MMR (no padding).
        lambda_: Relevance vs. diversity trade-off in [0.0, 1.0].
            * ``1.0`` -> pure relevance (top-k by score; ties broken by
              original order).
            * ``0.7`` -> relevance-dominant with diversity penalty on
              already-selected keys (default).
            * ``0.0`` -> maximal spread (pick one per unique diversity key
              before any key is hit twice; within a key, highest score).

    Returns:
        List of at most ``k`` items from ``scored_candidates``, re-ranked
        by the MMR criterion.  Original objects are returned (not copies).
    """
    if not scored_candidates:
        return []

    # Work on a local list so we can pop selected items. Sort by score
    # descending for deterministic tie-breaking.
    remaining = list(scored_candidates)
    remaining.sort(key=lambda c: -float(_get_score(c)))

    # Pre-compute diversity keys once — they don't change during selection.
    keys: dict[int, tuple[str, str, str]] = {
        id(c): _diversity_key(c) for c in remaining
    }

    selected: list = []
    selected_keys: set[tuple[str, str, str]] = set()

    effective_k = min(k, len(remaining))

    # lambda_=1.0 short-circuit: top-k by score, no overlap penalty.
    if lambda_ >= 1.0:
        return remaining[:effective_k]

    while len(selected) < effective_k and remaining:
        best_idx = -1
        best_value = -float("inf")
        for i, cand in enumerate(remaining):
            score = float(_get_score(cand))
            overlap = 1.0 if keys[id(cand)] in selected_keys else 0.0
            value = lambda_ * score - (1.0 - lambda_) * overlap
            if value > best_value:
                best_value = value
                best_idx = i
        if best_idx < 0:
            break
        winner = remaining.pop(best_idx)
        selected.append(winner)
        selected_keys.add(keys[id(winner)])

    return selected


def _get_score(obj: Any) -> float:
    """Extract numeric score; defaults to 0.0 if absent or non-numeric."""
    try:
        score = getattr(obj, "score", None)
        if score is None and isinstance(obj, dict):
            score = obj.get("score", 0.0)
        return float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
