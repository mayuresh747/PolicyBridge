"""GPT-5.1 answer synthesizer with streaming, legal hierarchy, and citations (Plan 04-04).

Implements the answer generation layer per D-05, D-06, D-08, D-09, D-10, D-11:
- Takes retrieval results, formats context with `[{citation}] {agency}` headers
- Streams GPT-5.1 response with inline `[CITATION]` citations (e.g. `[RCW 19.27.074]`)
- Applies legal hierarchy callouts (D-08) and conflict disclaimers (D-09)
- Assigns per-claim confidence from retrieval scores (D-07)
- Renders premise corrections in D-05 format when false premises detected
- Produces the complete AnswerResult (D-11)
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from src.config import (
    SYNTHESIS_LLM_MODEL,
    SYNTHESIS_MAX_TOKENS,
    SYNTHESIS_TEMPERATURE,
)
from src.query.confidence import assign_confidence
from src.query.context_builder import (
    build_context,
    detect_conflict_signals,
    detect_hierarchy_patterns,
    format_sources_summary,
)
from src.query.llm import LLMCallManager
from src.query.models import AnswerResult, ClaimResult, SourceRef
from src.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """\
You are a regulatory analysis assistant for Washington State and Seattle development codes.

## ROLE
Answer the user's question using ONLY the provided source documents. Be concise and precise. \
Every factual claim must cite its source using `[CITATION]` notation.

## CITATION RULES
- Cite `[CITATION]` inline immediately after each factual claim, where CITATION is the \
exact citation string from the source header (e.g. `[RCW 19.27.074]`, `[SMC 23.44.014(B)]`, \
`[WAC 51-11C-403]`).
- Copy the citation string verbatim from the bracketed header of the source you are \
quoting — never invent, abbreviate, or paraphrase a citation.
- For multiple citations at one fact, write each in its own brackets, space-separated: \
`[RCW 19.27.074] [WAC 51-11C-403]`.
- If two source headers share the same citation string, treat them as one citation — \
cite it once.
- If no source supports a claim, say "Not found in provided sources"

## LEGAL HIERARCHY (Washington State)
- Hierarchy: federal > RCW (state statute) > WAC (state admin rule) > SMC (local statute) \
> DIR (local admin rule) > SPU (guidance)
- RCW sets the floor; SMC may be MORE restrictive — flag this when it occurs
- WAC implements RCW — cite the enabling statute when relevant

{hierarchy_callouts}
{conflict_disclaimer}
{premise_correction}

## STRUCTURE RULES
Use the shortest structure that fully answers the question:

**Single-topic questions** — 2–4 sentences maximum. No headers. Direct answer + citation.

**Multi-part or list questions** — bullet points or numbered list. One bullet per requirement. \
No padding sentences.

**Comparisons or conflicts between agencies/rules** — use a markdown table:
| Agency | Rule | Requirement | Source |
|--------|------|-------------|--------|
Never describe a comparison in prose when a table fits.

**Dimensional standards, fees, thresholds** — always a table or list, never prose.

**Cross-agency questions** — short intro sentence (one line), then structured content. \
No lengthy preamble.

## FORMATTING RULES
- Regulatory code citations: wrap in backticks — `SMC 23.54.015.K`, `WAC 51-50-0101`, `RCW 36.70A`
- Specific values, measurements, thresholds: use **bold** — **1 space per 250 sq ft**, **30 percent**, **50 feet**
- Key limiting or conditional terms: use **bold** — **no minimum**, **prohibited**, **required**, **must**, **shall not**
- Do NOT bold entire sentences or long phrases — bold only the specific number, code, or qualifier

## CONFLICT AND RISK ANALYSIS
When sources marked "(POTENTIALLY CONFLICTING)" appear in context:
- Explicitly analyse the tension between the conflicting source and the source it \
conflicts with. Do not just summarise each independently.
- Identify which authority prevails under Washington State hierarchy rules.
- Flag if requirements from different agencies cannot both be satisfied simultaneously.

When the user asks about risks, conflicts, tensions, or unclear responsibilities:
- Add a **## Potential Conflicts & Risks** section at the end of your answer.
- Use a table for cross-agency comparisons when two or more agencies address the same topic:

| Issue | Agency A Requirement | Agency B Requirement | Tension |
|-------|---------------------|---------------------|---------|

- Note where the law is SILENT on a question the user asked — say "No source in the \
provided documents addresses [specific aspect]."
- Flag where responsibility allocation between parties (city vs. developer, state vs. \
local) is ambiguous or undefined in the retrieved sources.

## BREVITY RULES
- No preamble ("Great question", "To answer your question", "Based on the sources")
- No restating the question
- No closing summary paragraph — the sources list is auto-appended
- Cut any sentence that doesn't add a new fact
- If the answer is one sentence, write one sentence

{level_format_rules}
"""


# ---------------------------------------------------------------------------
# Premise correction builder (D-05)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Level-aware formatting rules (injected for L3+ to keep output structured)
# ---------------------------------------------------------------------------

_L3_PLUS_FORMAT_RULES = """\
## COMPLEX QUERY FORMAT (MANDATORY for this query)
This is a multi-part question. Follow these rules strictly:
- Lead with a **1-line summary** answering the core question directly.
- Use a **table** for ANY comparison between agencies, rules, standards, or requirements. \
Never describe a comparison in prose.
- Use **bullet points** (1-2 sentences each) for each sub-topic or requirement. No long paragraphs.
- No paragraph may exceed 2 sentences. If you need more, break into bullets or a table.
- Group related items under short **### sub-headers** (3-5 words max).
- Total answer length: aim for concise coverage, not exhaustive narration.
"""


def _build_premise_correction(premise_flag: dict | None) -> str:
    """Build premise correction instruction for the system prompt per D-05.

    When premise_flag is not None (and not empty), instructs the LLM to lead
    the answer with a warning and correction before the main answer.

    Args:
        premise_flag: Dict with keys 'premise', 'correction', 'source_citation',
            or None / empty dict.

    Returns:
        Premise correction block for the system prompt, or empty string.
    """
    if not premise_flag:
        return ""
    premise = premise_flag.get("premise", "")
    correction = premise_flag.get("correction", "")
    source_citation = premise_flag.get("source_citation", "")
    return (
        "## PREMISE CORRECTION (MANDATORY -- render this FIRST before answering)\n"
        "The user's question contains a false premise. You MUST lead your answer "
        "with this exact format:\n\n"
        f'Warning: Premise check: Your question states "{premise}". '
        f"However, {source_citation} establishes {correction}.\n\n"
        "To answer your actual question: ...\n\n"
        "Then proceed with the normal answer below the correction."
    )


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

# Match bracketed citations whose contents start with one of the agency anchors
# our corpus actually emits. Aligns with benchmarks/citation_normalize.py:38.
# Anchoring on the agency prefix prevents the regex from eating markdown
# constructs like `[click here](url)` or footnote markers like `[1]`.
_CITATION_RE = re.compile(
    r"\[((?:SMC|RCW|WAC|DIR|DR|IBC-WA|SPU|EO|Court|No\.|State\s+v\.)[^\[\]]*)\]"
)


def _extract_claims(
    answer_text: str, sources: list[SourceRef]
) -> list[ClaimResult]:
    """Extract `[CITATION]` references from answer text into ClaimResult objects.

    For each unique citation found, creates a ClaimResult with confidence
    assigned from the matching source's retrieval score. When multiple sources
    share the same citation string (rare; e.g. adjacent paragraphs of one
    section), the higher-score source wins. Citations the LLM emitted that
    don't appear in the source list (hallucinations) are silently skipped
    with a warning logged.

    Args:
        answer_text: The synthesized answer text with `[CITATION]` markers.
        sources: List of SourceRef objects from build_context.

    Returns:
        List of ClaimResult objects, one per unique citation cited.
    """
    found = _CITATION_RE.findall(answer_text)
    if not found:
        return []

    # Build citation -> [SourceRef] map (collisions allowed, dedupe later by score).
    source_map: dict[str, list[SourceRef]] = {}
    for s in sources:
        source_map.setdefault(s.citation, []).append(s)

    # Count occurrences per citation string.
    counts: dict[str, int] = {}
    for cite in found:
        counts[cite] = counts.get(cite, 0) + 1

    # Emit one claim per unique citation, in order of first appearance.
    seen: set[str] = set()
    claims: list[ClaimResult] = []
    for cite in found:
        if cite in seen:
            continue
        seen.add(cite)

        candidates = source_map.get(cite)
        if not candidates:
            logger.warning(
                "Hallucinated citation '%s' in answer text — not in source list",
                cite,
            )
            continue

        # On collision, pick the highest-score chunk for confidence calculation.
        source = max(candidates, key=lambda s: s.score)
        confidence = assign_confidence(source.score, counts[cite])
        claims.append(
            ClaimResult(
                id=source.source_num,
                citation=source.citation,
                page=source.page,
                confidence=confidence,
                excerpt=source.text_excerpt,
            )
        )

    return claims


# ---------------------------------------------------------------------------
# Main synthesizer
# ---------------------------------------------------------------------------


async def synthesize_answer(
    query: str,
    results: list[RetrievalResult],
    llm: LLMCallManager,
    session_context: list[dict] | None = None,
    premise_flag: dict | None = None,
    query_level: str = "L1",
    session_id: str = "",
    audit_mode: bool = False,
    context_preamble: str = "",
) -> AsyncIterator[dict]:
    """Stream GPT-5.1 answer synthesis with per-claim citations.

    Yields SSE-compatible events:
    - {"type": "token", "data": "chunk of text"}
    - {"type": "usage", "data": {"prompt_tokens": N, "completion_tokens": N}}
    - {"type": "result", "data": AnswerResult}  -- final complete result

    Args:
        query: The user's question.
        results: List of RetrievalResult from the retrieval engine.
        llm: LLMCallManager instance for making API calls.
        session_context: Optional list of prior turn dicts for multi-turn.
        premise_flag: Optional premise correction data (D-05).
        query_level: Classification level "L1" through "L6".
        session_id: Session identifier.

    Yields:
        Dict events for SSE streaming.
    """
    # 1. Build numbered context and source mapping
    context, source_refs = build_context(results)

    # 2. Detect legal hierarchy patterns (D-08)
    hierarchy_callouts = detect_hierarchy_patterns(source_refs)
    hierarchy_text = ""
    if hierarchy_callouts:
        hierarchy_text = (
            "## SPECIFIC HIERARCHY CALLOUTS FOR THIS QUERY\n"
            + "\n".join(f"- {c}" for c in hierarchy_callouts)
        )

    # 3. Detect conflict signals (D-09)
    conflict_text = ""
    conflict_signal = detect_conflict_signals(source_refs)
    if conflict_signal:
        conflict_text = (
            "## CONFLICT WARNING\n"
            f"{conflict_signal}"
        )

    # 4. Build premise correction block (D-05)
    premise_text = _build_premise_correction(premise_flag)

    # 5. Assemble system prompt
    level_format = _L3_PLUS_FORMAT_RULES if query_level not in ("L1", "L2") else ""
    system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(
        hierarchy_callouts=hierarchy_text,
        conflict_disclaimer=conflict_text,
        premise_correction=premise_text,
        level_format_rules=level_format,
    )

    # 6. Build messages list
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Include session context (last 5 turns) if provided
    if session_context:
        for turn in session_context[-5:]:
            messages.append(turn)

    # User message with context. When GRAPH_FEATURE_COMPOSER is on, the
    # pipeline prepends an S6 relational preamble (plain-text traversal
    # narration) ahead of the numbered source blocks. Flag-off passes an
    # empty string and the prompt shape is byte-for-byte legacy.
    context_prefix = f"{context_preamble}\n\n" if context_preamble else ""
    user_content = f"Context:\n{context_prefix}{context}\n\nQuestion: {query}"
    messages.append({"role": "user", "content": user_content})

    # Always emit LLM I/O snapshot for always-on trace capture (D-15).
    # Non-audit clients ignore unknown event types; audit clients render it live.
    yield {
        "type": "audit_llm_io",
        "data": {
            "stage": "llm_io",
            "elapsed_ms": 0,
            "input": {
                "model": SYNTHESIS_LLM_MODEL,
                "system_prompt": system_prompt,
                "context_message": user_content[:2000],
                "context_length_chars": len(user_content),
                "num_sources": len(source_refs),
                "temperature": SYNTHESIS_TEMPERATURE,
                "max_tokens": SYNTHESIS_MAX_TOKENS,
            },
            "output": {},
        },
    }

    # 7. Stream from LLM
    stream = await llm.stream(
        model=SYNTHESIS_LLM_MODEL,
        messages=messages,
        temperature=SYNTHESIS_TEMPERATURE,
        max_tokens=SYNTHESIS_MAX_TOKENS,
    )

    # 8. Iterate over stream chunks
    full_answer_parts: list[str] = []
    usage_data: dict | None = None

    async for chunk in stream:
        # Token content
        if chunk.choices:
            for choice in chunk.choices:
                delta_content = choice.delta.content
                if delta_content:
                    full_answer_parts.append(delta_content)
                    yield {"type": "token", "data": delta_content}

        # Usage stats from final chunk
        if hasattr(chunk, "usage") and chunk.usage is not None:
            usage_data = {
                "prompt_tokens": chunk.usage.prompt_tokens or 0,
                "completion_tokens": chunk.usage.completion_tokens or 0,
            }

    # 9. Yield usage event
    if usage_data:
        yield {"type": "usage", "data": usage_data}

    # 10. Post-processing
    answer_text = "".join(full_answer_parts)

    # Extract claims with confidence
    claims = _extract_claims(answer_text, source_refs)

    # Append sources summary per D-10
    sources_summary = format_sources_summary(source_refs)
    answer_text = f"{answer_text}\n\n---\n{sources_summary}"

    # Build final AnswerResult (D-11)
    result = AnswerResult(
        answer_text=answer_text,
        claims=claims,
        sources=source_refs,
        premise_flag=premise_flag,
        session_id=session_id,
        query_level=query_level,
    )

    yield {"type": "result", "data": result}
