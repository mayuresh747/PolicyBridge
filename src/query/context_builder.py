"""Context builder for the answer synthesizer (Plan 04-04).

Adapts the existing RAG Agent pattern (D-06): keys retrieved chunks
by their citation as [CITATION] AGENCY, groups by authority rank (higher first),
and produces the context block consumed by GPT-5.1. The LLM cites each fact
inline using the bracketed citation (e.g. `[RCW 19.27.074]`); SourceRef.source_num
is preserved as an internal ordinal for the sidebar's numbered manifest.

Also provides:
- format_sources_summary: brief D-10 format sources list appended to answers
- detect_hierarchy_patterns: legal hierarchy callouts (D-08)
- detect_conflict_signals: inter-agency conflict disclaimers (D-09)
- enforce_token_budget: hard-cap token budget gate before synthesis
"""

from __future__ import annotations

import logging

import tiktoken

from src.config import (
    AUTHORITY_HIERARCHY,
    CONFLICT_BUDGET_RESERVE,
    SYNTHESIS_CONTEXT_MAX_TOKENS,
)
from src.query.models import SourceRef
from src.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)

# Lazy-initialized encoder (deferred to avoid network call at import time)
_enc: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    """Return the cl100k_base encoder, initializing on first use."""
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def build_context(
    results: list[RetrievalResult],
) -> tuple[str, list[SourceRef]]:
    """Build citation-keyed context block and source mapping.

    Each chunk header is `[{citation}] {agency}` so the LLM cites facts
    inline using the bracketed citation string. Groups by authority rank
    (higher authority first per AUTHORITY_HIERARCHY); within an authority
    tier, higher score wins.

    Args:
        results: List of RetrievalResult from the retrieval engine.

    Returns:
        Tuple of (context_string, source_refs). source_refs.source_num
        retains 1..N ordering for sidebar enumeration; the LLM cites by
        SourceRef.citation, not source_num.
    """
    if not results:
        return "(No relevant documents found.)", []

    # Sort by authority level (higher authority first), then by score descending
    sorted_results = sorted(
        results,
        key=lambda r: (
            AUTHORITY_HIERARCHY.get(r.authority_level, 99),
            -r.score,
        ),
    )

    sources: list[SourceRef] = []
    blocks: list[str] = []
    for i, r in enumerate(sorted_results, 1):
        sources.append(
            SourceRef(
                source_num=i,
                citation=r.citation,
                agency=r.agency,
                authority_level=r.authority_level,
                page=None,  # page number not available in current RetrievalResult
                chunk_id=r.chunk_id,
                score=r.score,
                text_excerpt=r.text[:200],
            )
        )
        header = f"[{r.citation}] {r.agency}"
        if r.section_title:
            header += f", {r.section_title}"
        # Tag conflict-expanded chunks so GPT-5.1 knows to analyse tension
        if "conflict_expand" in (r.retrieval_sources or []):
            provenance = ""
            if r.graph_context:
                ctx = r.graph_context[0] if r.graph_context else {}
                shared = ctx.get("shared_authority_target", "")
                approach = ctx.get("source_approach", "")
                if shared:
                    provenance = f" -- shares authority with {shared}"
                elif approach == "cross_agency_vector":
                    provenance = " -- same topic, different authority"
            header += f" (POTENTIALLY CONFLICTING{provenance})"
        blocks.append(f'{header}\n"{r.text}"')

    context = "\n\n---\n\n".join(blocks)
    return context, sources


def format_sources_summary(sources: list[SourceRef]) -> str:
    """Brief sources summary for API/testing use (appended to answer).

    Format per D-10:
        Sources: [1] SMC 23.44.014(B) -- Setback requirements, [2] RCW 36.70A.040 -- GMA goals

    Args:
        sources: List of SourceRef objects from build_context.

    Returns:
        Formatted sources summary string.
    """
    parts = []
    for s in sources:
        part = f"[{s.source_num}] {s.citation}"
        if s.text_excerpt:
            part += f" -- {s.text_excerpt[:50]}"
        parts.append(part)
    return "Sources: " + ", ".join(parts)


def detect_hierarchy_patterns(sources: list[SourceRef]) -> list[str]:
    """Detect legal hierarchy patterns in retrieved sources (D-08).

    Returns callout strings for the synthesizer prompt when sources span
    multiple levels of the Washington legal authority hierarchy.

    Patterns detected:
    - WAC + RCW pair: "WAC {x} implements the authority granted by RCW {y}"
    - RCW + SMC/DIR pair: "state law (RCW) preempts local code (SMC/DIR) on this point"
    - SMC stricter than WAC: "SMC may be more restrictive than the state minimum"

    Args:
        sources: List of SourceRef objects.

    Returns:
        List of callout strings (empty if no patterns detected).
    """
    callouts: list[str] = []

    # Group sources by authority_level
    by_level: dict[str, list[SourceRef]] = {}
    for s in sources:
        by_level.setdefault(s.authority_level, []).append(s)

    # Check for WAC (state_admin_rule) + RCW (state_statute) pair
    wac_sources = by_level.get("state_admin_rule", [])
    rcw_sources = by_level.get("state_statute", [])
    if wac_sources and rcw_sources:
        wac_cite = wac_sources[0].citation
        rcw_cite = rcw_sources[0].citation
        callouts.append(
            f"Note: {wac_cite} implements the authority granted by {rcw_cite}. "
            f"Cite the enabling statute when referencing the administrative rule."
        )

    # Check for RCW (state_statute) + SMC/DIR (local) pair
    local_sources = by_level.get("local_statute", []) + by_level.get(
        "local_admin_rule", []
    )
    if rcw_sources and local_sources:
        rcw_cite = rcw_sources[0].citation
        local_cite = local_sources[0].citation
        callouts.append(
            f"Note: State law ({rcw_cite}) preempts local code ({local_cite}) "
            f"on this point -- the RCW sets the floor. "
            f"SMC may be more restrictive than the state minimum."
        )

    return callouts


def detect_conflict_signals(sources: list[SourceRef]) -> str | None:
    """Detect potential conflicts between sources from different agencies (D-09).

    Soft signal based on retrieval evidence -- not pre-computed CONFLICTS_WITH edges.
    Returns a conflict disclaimer when sources span 2+ agencies with different
    authority levels and both have scores above the relevance threshold.

    Args:
        sources: List of SourceRef objects.

    Returns:
        Conflict disclaimer string, or None if no conflict signals.
    """
    if not sources:
        return None

    # Filter to high-relevance sources (score > 0.5)
    relevant = [s for s in sources if s.score > 0.5]
    if len(relevant) < 2:
        return None

    # Group relevant sources by agency
    agencies: dict[str, list[SourceRef]] = {}
    for s in relevant:
        agencies.setdefault(s.agency, []).append(s)

    if len(agencies) < 2:
        return None

    # Check for authority level differences across agencies
    authority_levels = set()
    for s in relevant:
        authority_levels.add(
            AUTHORITY_HIERARCHY.get(s.authority_level, 99)
        )

    # Require meaningful authority difference (gap >= 3 levels)
    if len(authority_levels) >= 2:
        level_range = max(authority_levels) - min(authority_levels)
        if level_range >= 3:
            agency_names = ", ".join(sorted(agencies.keys()))
            return (
                f"These requirements may conflict across agencies ({agency_names}). "
                f"State hierarchy rules apply -- higher authority prevails where "
                f"inconsistent. Consult legal counsel for your specific situation."
            )

    return None


# ---------------------------------------------------------------------------
# Token budget enforcement
# ---------------------------------------------------------------------------

# Trim priority: lowest-value sources removed first.
_TRIM_PRIORITY = {
    "conflict_expand": 0,  # newest, least proven — trim first
    "graph_expand": 1,
    "cache": 2,
    "graph": 3,
    "bm25": 4,
    "vector": 5,           # highest value — trim last
}


def _trim_priority_key(r: RetrievalResult) -> tuple[int, float]:
    """Return (priority, -score) for trim ordering.

    Lower priority number = trimmed first.  Within the same priority,
    lower score is trimmed first.
    """
    sources = r.retrieval_sources or []
    # Use the highest-value source tag the chunk has
    best = max((_TRIM_PRIORITY.get(s, 3) for s in sources), default=3)
    return (best, -r.score)


def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base (matches text-embedding-3-large)."""
    return len(_get_encoder().encode(text))


def count_tokens_for_audit(text: str) -> int:
    """Public wrapper for _count_tokens for audit use."""
    return _count_tokens(text)


def enforce_token_budget(
    results: list[RetrievalResult],
    max_tokens: int = SYNTHESIS_CONTEXT_MAX_TOKENS,
    level: str = "L1",
) -> tuple[list[RetrievalResult], dict]:
    """Trim results to fit within the synthesis token budget.

    Counts tokens for every chunk's text.  If the total exceeds
    ``max_tokens``, removes the lowest-priority chunks (by retrieval
    source type, then by score) until the budget is met.

    For L3+ queries, up to ``CONFLICT_BUDGET_RESERVE`` conflict_expand
    chunks are reserved before trimming and re-injected afterward,
    ensuring the system's core differentiator (cross-agency conflict
    detection) is never sacrificed for budget reasons.

    Priority order (trimmed first -> last, L1/L2):
        conflict_expand -> graph_expand -> cache -> graph -> bm25 -> vector

    For L3+, reserved conflict_expand chunks are exempt from this ordering.

    Args:
        results: All RetrievalResult objects headed for synthesis.
        max_tokens: Hard cap on total chunk text tokens.
        level: Query complexity level (L1-L6). L3+ reserves conflict chunks.

    Returns:
        Tuple of (trimmed_results, budget_report).  budget_report is a dict
        with keys: total_before, total_after, chunks_before, chunks_after,
        trimmed, trimmed_sources, conflict_reserved.
    """
    if not results:
        return results, {
            "total_before": 0, "total_after": 0,
            "chunks_before": 0, "chunks_after": 0,
            "trimmed": 0, "trimmed_sources": {},
            "conflict_reserved": 0,
        }

    # For L3+ queries, reserve up to CONFLICT_BUDGET_RESERVE conflict_expand
    # chunks -- these are exempt from trimming (the system's core differentiator).
    conflict_reserved: list[RetrievalResult] = []
    if level not in ("L1", "L2"):
        conflict_chunks = [r for r in results if "conflict_expand" in (r.retrieval_sources or [])]
        conflict_reserved = conflict_chunks[:CONFLICT_BUDGET_RESERVE]
        if conflict_reserved:
            reserved_ids = {id(r) for r in conflict_reserved}
            results = [r for r in results if id(r) not in reserved_ids]

    # Count tokens per chunk
    token_counts: list[tuple[RetrievalResult, int]] = [
        (r, _count_tokens(r.text)) for r in results
    ]
    total_before = sum(tc for _, tc in token_counts)

    if total_before <= max_tokens:
        # Under budget — pass through (re-inject any reserved conflict chunks)
        if conflict_reserved:
            results.extend(conflict_reserved)
        return results, {
            "total_before": total_before,
            "total_after": total_before,
            "chunks_before": len(results),
            "chunks_after": len(results),
            "trimmed": 0,
            "trimmed_sources": {},
            "conflict_reserved": len(conflict_reserved),
        }

    # Over budget — sort by trim priority (lowest value first)
    indexed = [(r, tc, _trim_priority_key(r)) for r, tc in token_counts]
    indexed.sort(key=lambda x: x[2])

    # Remove from the front (lowest priority) until under budget
    running_total = total_before
    trim_idx = 0
    trimmed_sources: dict[str, int] = {}
    trimmed_chunks: list[dict] = []

    while running_total > max_tokens and trim_idx < len(indexed):
        r, tc, _ = indexed[trim_idx]
        running_total -= tc
        # Track what category was trimmed
        src_tag = (r.retrieval_sources or ["unknown"])[0]
        trimmed_sources[src_tag] = trimmed_sources.get(src_tag, 0) + 1
        trimmed_chunks.append({
            "citation": r.citation,
            "priority_tier": _trim_priority_key(r)[0],
            "tokens": tc,
            "retrieval_sources": r.retrieval_sources,
        })
        trim_idx += 1

    # Kept chunks are everything from trim_idx onward
    kept = [r for r, _, _ in indexed[trim_idx:]]

    # Re-sort kept chunks by authority hierarchy + score (preserve display order)
    kept.sort(
        key=lambda r: (AUTHORITY_HIERARCHY.get(r.authority_level, 99), -r.score)
    )

    # Re-inject reserved conflict chunks (exempt from trimming for L3+)
    if conflict_reserved:
        kept.extend(conflict_reserved)

    report = {
        "total_before": total_before,
        "total_after": running_total,
        "chunks_before": len(results),
        "chunks_after": len(kept),
        "trimmed": trim_idx,
        "trimmed_sources": trimmed_sources,
        "trimmed_chunks": trimmed_chunks,
        "conflict_reserved": len(conflict_reserved),
    }

    logger.info(
        "Token budget: %d→%d tokens, %d→%d chunks (trimmed %d: %s)",
        total_before, running_total, len(results), len(kept),
        trim_idx, trimmed_sources,
    )

    return kept, report
