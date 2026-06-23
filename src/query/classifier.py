"""Query complexity classifier (L1-L6) using GPT-4.1-mini (D-01, D-02, D-03).

Classifies incoming queries into complexity levels to determine the
retrieval strategy:
  - L1-L2: Direct retrieve() call
  - L3+:   RT-RAG binary tree decomposition
  - L6:    Premise scan before answering

One LLM call returns both the level and premise_scan_needed flag (D-03).
"""

from __future__ import annotations

import json
import logging

from src.config import QUERY_LLM_MODEL
from src.query.llm import LLMCallManager
from src.query.models import ClassificationResult

logger = logging.getLogger(__name__)

_VALID_LEVELS = {"L1", "L2", "L3", "L4", "L5", "L6"}

CLASSIFIER_SYSTEM_PROMPT = """\
You classify regulatory queries about Washington State and Seattle development codes into complexity levels.

Levels:
- L1: Direct lookup -- single section, single agency (e.g., "What are the two conditions under WAC 365-196-875?")
- L2: Multi-fact, single agency (e.g., "What are all parking requirements in SMC?")
- L3: Two-part decomposition needed, possibly cross-agency
- L4: Multi-step reasoning chain, cross-agency, sequential dependencies, or multi-part bundled questions
- L5: Deep conditional/hypothetical with nested conditions changing which rules apply
- L6: Contains a false or questionable premise about existing rules

Return JSON:
{"level": "L1", "premise_scan_needed": false, "conflict_seeking": false, "reasoning": "Single section lookup for WAC conditions"}

Rules:
- If the query contains a premise that might be false (claims about rules that may not exist or are stated incorrectly), set premise_scan_needed to true AND set level to "L6".
- A query referencing multiple agencies or needing cross-reference analysis is at least L3.
- Questions with "and" joining distinct sub-questions are at least L3.
- Hypotheticals with "if... then what about..." nested conditions are L5.
- If the query asks about risks, conflicts, tensions, unclear responsibilities, contradictions between agencies, overlapping jurisdiction, regulatory gaps, or who is liable/responsible, set conflict_seeking to true. This is independent of the level -- even an L2 question can be conflict_seeking."""


async def classify_query(query: str, llm: LLMCallManager) -> ClassificationResult:
    """Classify a user query into complexity level L1-L6.

    Uses a single GPT-4.1-mini call with json_object format at temperature=0.0.
    Returns both the complexity level and whether a premise scan is needed.

    On JSON parse error or invalid level, falls back to L2 with
    premise_scan_needed=False.

    Args:
        query: The user's regulatory query text.
        llm: Shared LLMCallManager instance.

    Returns:
        ClassificationResult with level, premise_scan_needed, and reasoning.
    """
    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    try:
        raw = await llm.call(
            model=QUERY_LLM_MODEL,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Classifier JSON parse error: %s", exc)
        return ClassificationResult(
            level="L2",
            premise_scan_needed=False,
            reasoning="fallback: invalid classifier response",
        )

    level = data.get("level", "L2")
    if level not in _VALID_LEVELS:
        logger.warning("Classifier returned invalid level %r, defaulting to L2", level)
        level = "L2"

    premise_scan_needed = bool(data.get("premise_scan_needed", False))
    conflict_seeking = bool(data.get("conflict_seeking", False))
    reasoning = data.get("reasoning", "") or f"Classified as {level}"

    return ClassificationResult(
        level=level,
        premise_scan_needed=premise_scan_needed,
        reasoning=reasoning,
        conflict_seeking=conflict_seeking,
    )
