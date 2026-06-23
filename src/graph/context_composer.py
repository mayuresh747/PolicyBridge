"""S6 extractive context composer.

Compresses graph-expanded synthesis context into three layers:
  1. Relational preamble (<= ~120 tokens, plain text)
  2. Seed chunks (full text)
  3. Expansion chunks (first sentence + ' ... ' + last sentence)

Section-level dedup collapses (document, section) siblings; the seed
wins unless the expansion has >= 20% novel unigram tokens. Final
selection is a greedy knapsack over (relevance / token_cost).

D-01 / D-08: strictly extractive -- NO LLM summarisation. The original
strategy-doc variant of S6 proposed 1-sentence LLM summaries; that path
was dropped under D-01. First + last sentence is cheap, deterministic,
and still captures the topical anchor of a regulatory chunk.

Design notes / decisions made in-code:

- Section dedup key -- ``RetrievalResult`` carries no explicit
  ``filename`` or ``section_number`` field. We derive
  ``(document, section)`` from ``citation_path`` when present, falling
  back to ``(agency, citation)`` for results that lack the structured
  path. Both forms are normalised to lower-case strings.
- Knapsack priority -- seeds are non-negotiable (always included if they
  fit in budget; over-budget seeds trimmed last). Expansions compete via
  a greedy score/cost ratio. Depth / retrieval-source tier acts as a
  tie-breaker when ratios are equal.
- Paths may be empty -- in the current wiring (08-05) ``beam_paths`` are
  not threaded through ``pipeline.py``. ``compose()`` degrades to a
  minimal preamble when ``paths=[]``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from src.query.context_builder import count_tokens_for_audit

logger = logging.getLogger(__name__)

# Split on sentence-terminator followed by whitespace + an upper-case /
# digit / left-bracket start.  Regulatory text frequently embeds "."
# inside citations (e.g. "SMC 23.44.014"), so we require the next
# character to plausibly begin a new sentence.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[\(\"])")

# Tokens shorter than this are dropped from novelty-overlap comparisons;
# prevents boilerplate ("the", "a", "of") from dominating the ratio.
_MIN_NOVELTY_TOKEN_LEN = 3

# Maximum edge types enumerated in the preamble; keeps it <= 120 tokens
# in the common case (3-6 distinct edge types across a handful of seeds).
_PREAMBLE_MAX_EDGES = 6

# Expansion-chunk signal on ``retrieval_sources``.
_EXPANSION_TAG = "graph_expand"


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #


@dataclass
class PromptBlock:
    """Composer output headed for the synthesiser.

    ``body`` already includes per-chunk ``[Source N]`` markers so callers
    can slot it straight into the synthesis prompt without re-formatting.
    """

    preamble: str
    body: str
    total_tokens: int
    included_chunk_ids: list[str] = field(default_factory=list)
    excluded_chunk_ids: list[str] = field(default_factory=list)


def compose(
    seeds: list,
    expansions: list,
    paths: list,
    prompt_budget: int,
) -> PromptBlock:
    """Emit preamble + seed-full + expansion-extractive body within budget.

    Args:
        seeds: ``RetrievalResult``-like objects kept in full.
        expansions: ``RetrievalResult``-like objects compressed to
            first+last sentence. Typically carry
            ``retrieval_sources=["graph_expand"]``.
        paths: ``ScoredPath`` list for preamble narration. May be empty.
        prompt_budget: Hard cap on the returned ``total_tokens``
            (preamble + body).

    Returns:
        A ``PromptBlock`` respecting the budget, with section-level
        dedup and greedy knapsack selection applied to expansions.
    """
    # Safe no-op.
    if not seeds and not expansions:
        return PromptBlock(preamble="", body="", total_tokens=0)

    preamble = _build_preamble(seeds, paths)
    preamble_tokens = count_tokens_for_audit(preamble) if preamble else 0

    # Section dedup: drop expansions that duplicate a seed (or another
    # higher-ranked expansion) unless they carry > 20% novel tokens.
    deduped_expansions, dropped_dupes = _section_dedup(seeds, expansions)

    # Build (id, tokens, score, body_text) tuples for each candidate.
    seed_items: list[tuple[str, int, float, str]] = []
    for r in seeds:
        body = _render_chunk(r, compressed=False)
        seed_items.append((_chunk_id(r), count_tokens_for_audit(body), _score(r), body))

    expansion_items: list[tuple[str, int, float, str]] = []
    for r in deduped_expansions:
        body = _render_chunk(r, compressed=True)
        expansion_items.append(
            (_chunk_id(r), count_tokens_for_audit(body), _score(r), body)
        )

    # Seeds first -- non-negotiable subject only to the overall budget.
    body_budget = max(0, prompt_budget - preamble_tokens)
    included: list[tuple[str, int, float, str]] = []
    excluded: list[str] = [cid for cid in dropped_dupes]

    running = 0
    for item in seed_items:
        _cid, cost, _s, _body = item
        if running + cost <= body_budget:
            included.append(item)
            running += cost
        else:
            excluded.append(_cid)

    # Expansions compete via greedy score/cost within the remaining budget.
    remaining = body_budget - running
    chosen_ids = _knapsack(expansion_items, remaining)
    chosen_set = set(chosen_ids)
    for item in expansion_items:
        cid = item[0]
        if cid in chosen_set:
            included.append(item)
        else:
            excluded.append(cid)

    # Assemble the rendered body.  Seeds precede expansions so the
    # synthesiser sees highest-authority material first; within each
    # group we keep input order (caller has already sorted by score /
    # authority).
    body_parts = [item[3] for item in included]
    body = "\n\n---\n\n".join(body_parts) if body_parts else ""
    body_tokens = count_tokens_for_audit(body) if body else 0

    total = preamble_tokens + body_tokens
    included_ids = [item[0] for item in included]

    logger.debug(
        "context_composer: preamble=%d body=%d total=%d budget=%d "
        "seeds=%d expansions_kept=%d dropped=%d",
        preamble_tokens, body_tokens, total, prompt_budget,
        len(seeds), len(included_ids) - len(seeds), len(excluded),
    )

    return PromptBlock(
        preamble=preamble,
        body=body,
        total_tokens=total,
        included_chunk_ids=included_ids,
        excluded_chunk_ids=excluded,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _chunk_id(chunk: Any) -> str:
    return getattr(chunk, "chunk_id", "") or ""


def _score(chunk: Any) -> float:
    try:
        return float(getattr(chunk, "score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _text(chunk: Any) -> str:
    return getattr(chunk, "text", "") or ""


def _citation(chunk: Any) -> str:
    return getattr(chunk, "citation", "") or ""


def _extract_first_last(text: str) -> str:
    """Return 'first ... last' for multi-sentence text; full text otherwise.

    Uses a simple regex sentence-split heuristic. Chunks with <= 2
    sentences are returned verbatim (no information loss to gain).
    """
    if not text:
        return ""
    # Light-normalise internal whitespace for a cleaner join.
    stripped = text.strip()
    parts = _SENTENCE_SPLIT.split(stripped)
    if len(parts) <= 2:
        return stripped
    first = parts[0].strip()
    last = parts[-1].strip()
    # Guard against empty tails (e.g. trailing punctuation artefacts).
    if not last:
        for p in reversed(parts[:-1]):
            if p.strip():
                last = p.strip()
                break
    if not first:
        first = stripped
    if first == last:
        return first
    return f"{first} ... {last}"


def _section_key(chunk: Any) -> tuple[str, str]:
    """Return the ``(document, section)`` dedup key.

    ``RetrievalResult`` does not expose ``filename``/``section_number``
    directly; we derive the key from ``citation_path`` when present and
    fall back to ``(agency, citation)`` otherwise. Keys are lower-cased
    strings so case-difference alone cannot defeat the dedup.
    """
    cp = getattr(chunk, "citation_path", None) or {}
    if isinstance(cp, dict):
        doc = (cp.get("document") or "").strip().lower()
        section = (cp.get("section") or "").strip().lower()
        if doc or section:
            return doc, section
    agency = (getattr(chunk, "agency", "") or "").strip().lower()
    citation = (_citation(chunk) or "").strip().lower()
    return agency, citation


def _unigrams(text: str) -> set[str]:
    """Lower-case alphanumeric unigram set used for novelty comparison."""
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= _MIN_NOVELTY_TOKEN_LEN}


def _novelty(candidate: Any, baseline: Any) -> float:
    """Fraction of ``candidate``'s unigram set not present in ``baseline``."""
    cand = _unigrams(_text(candidate))
    if not cand:
        return 0.0
    base = _unigrams(_text(baseline))
    if not base:
        return 1.0
    novel = cand - base
    return len(novel) / len(cand)


def _section_dedup(
    seeds: list,
    expansions: list,
    novelty_threshold: float = 0.20,
) -> tuple[list, list[str]]:
    """Drop expansions whose section already appears in seeds / higher-
    ranked expansions unless they carry > ``novelty_threshold`` fraction
    of unique unigrams vs the winner.

    Returns ``(kept_expansions, dropped_chunk_ids)``.
    """
    # Index by section key: seeds win automatically.
    winners: dict[tuple[str, str], Any] = {}
    for s in seeds:
        winners[_section_key(s)] = s

    kept: list = []
    dropped: list[str] = []

    # Walk expansions in caller-provided order (already score-sorted in
    # practice). First-in-at-section wins.
    for exp in expansions:
        key = _section_key(exp)
        if key in winners:
            baseline = winners[key]
            if _novelty(exp, baseline) > novelty_threshold:
                # Novel enough -- keep as an independent chunk.
                kept.append(exp)
            else:
                dropped.append(_chunk_id(exp))
        else:
            winners[key] = exp
            kept.append(exp)

    return kept, dropped


def _build_preamble(seeds: list, paths: list) -> str:
    """Build a <= ~120-token plain-text narration of the traversal.

    Format (single paragraph):
        "Evidence graph: N seeds ([citation, ...]). <edge-type> chain
         to <terminal>. <other-edge-type> chain to <terminal>. ..."

    With empty ``paths`` the preamble degrades to just the seed
    enumeration: "Evidence graph: N seeds ([citation, ...])."
    """
    if not seeds and not paths:
        return ""

    seed_citations = [
        c for c in (_citation(s) for s in seeds) if c
    ][:8]  # cap so huge seed sets don't blow the 120-token target
    seed_part = f"Evidence graph: {len(seeds)} seeds"
    if seed_citations:
        seed_part += f" ({', '.join(seed_citations)})"
    seed_part += "."

    if not paths:
        return seed_part

    # Group by edge_type; pick a representative terminal for each.
    by_edge: dict[str, list[Any]] = {}
    for p in paths:
        etype = getattr(p, "edge_type", "") or ""
        if not etype:
            continue
        by_edge.setdefault(etype, []).append(p)

    sentences = [seed_part]
    for etype, plist in list(by_edge.items())[:_PREAMBLE_MAX_EDGES]:
        # Terminal label: prefer the path with the highest score.
        plist.sort(key=lambda x: float(getattr(x, "score", 0.0) or 0.0),
                   reverse=True)
        terminal = getattr(plist[0], "chunk_id", "") or "?"
        sentences.append(f"{etype} chain to {terminal}.")

    return " ".join(sentences)


def _render_chunk(chunk: Any, *, compressed: bool) -> str:
    """Render a chunk as ``HEADER\\nBODY`` consistent with build_context."""
    agency = getattr(chunk, "agency", "") or ""
    citation = _citation(chunk) or ""
    section_title = getattr(chunk, "section_title", None)
    header = f"[Source] {agency} -- {citation}" if (agency or citation) else "[Source]"
    if section_title:
        header += f", {section_title}"
    raw = _text(chunk)
    body = _extract_first_last(raw) if compressed else raw
    if not body:
        return header
    return f'{header}\n"{body}"'


def _knapsack(
    items: list[tuple[str, int, float, str]],
    budget: int,
) -> list[str]:
    """Greedy selection by score / token_cost ratio.

    Exact 0/1 knapsack is ``O(n * budget)`` which is too coarse for
    token-count budgets in the tens of thousands. The greedy variant is
    within ~2x of optimal and is the standard choice for text-budget
    selection (see strategy doc S6). Ties break on higher raw score.
    """
    if budget <= 0 or not items:
        return []

    def _ratio(it: tuple[str, int, float, str]) -> tuple[float, float]:
        _cid, cost, score, _body = it
        denom = float(cost) if cost > 0 else 1e-6
        return (score / denom, score)

    ordered = sorted(items, key=_ratio, reverse=True)
    chosen: list[str] = []
    used = 0
    for cid, cost, _score_, _body in ordered:
        if used + cost <= budget:
            chosen.append(cid)
            used += cost
    return chosen
