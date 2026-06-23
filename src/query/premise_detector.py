"""Adversarial premise detector — two-stage detection for false-premise queries.

Stage 1 (scan_premise): GPT-4.1-mini quick-scans every query for suspicious
premises (~200ms). Returns a PremiseResult indicating whether a premise was
found and, if so, a verification_query to check against real documents.

Stage 2 (verify_premise): Only called when scan detects a premise.  Runs a
targeted retrieve() against the knowledge base.  If the top result contradicts
the premise (score >= 0.3), populates correction + source_citation.

Requirement: QRY-03 — Handle adversarial/trick questions that assume incorrect
premises.
"""

from __future__ import annotations

import asyncio
import json
import logging

from src.config import QUERY_LLM_MODEL
from src.query.llm import LLMCallManager
from src.query.models import PremiseResult
from src.retrieval.hybrid import retrieve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PREMISE_SCAN_PROMPT = """\
You analyze regulatory queries about Washington State and Seattle development codes for false premises.

A false premise is when the user states or assumes something about existing rules that is factually incorrect.

Examples of false premises:
- "Since Seattle has no minimum parking dimensions..." (Seattle SMC 23.54.030 DOES establish parking minimums)
- "Given that ADUs are banned in single-family zones..." (SMC 23.44.041 explicitly permits ADUs)
- "Because WAC doesn't address critical areas..." (WAC 365-196-410 directly addresses critical areas)

NOT false premises (these are legitimate questions):
- "What are the parking requirements?" (asking, not assuming)
- "Can I build an ADU in a single-family zone?" (asking, not assuming)
- "Does the Director have waiver authority?" (asking, not assuming)

Return JSON:
{"has_premise": true/false, "premise": "the stated premise or empty string", "verification_query": "search query to verify the premise or empty string"}

If the query simply asks a question without asserting facts, return has_premise: false."""


# ---------------------------------------------------------------------------
# Stage 1: scan_premise
# ---------------------------------------------------------------------------


async def scan_premise(query: str, llm: LLMCallManager) -> PremiseResult:
    """Quick-scan a query for false premises via LLM (~200ms).

    Args:
        query: The user's raw query string.
        llm: LLMCallManager (or mock) for making the LLM call.

    Returns:
        PremiseResult with has_premise=True if a suspicious premise was
        detected, along with the extracted premise and verification_query.
        On any error, returns a safe fallback with has_premise=False.
    """
    try:
        raw_response = await llm.call(
            model=QUERY_LLM_MODEL,
            messages=[
                {"role": "system", "content": PREMISE_SCAN_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        # Canonical LLMCallManager.call() returns a raw string.
        # Parse JSON from the response.
        if isinstance(raw_response, str):
            response = json.loads(raw_response)
        elif isinstance(raw_response, dict):
            response = raw_response
        else:
            logger.warning(
                "scan_premise: LLM returned unexpected type %s, falling back",
                type(raw_response).__name__,
            )
            return PremiseResult(
                has_premise=False, premise="", verification_query="",
                correction=None, source_citation=None,
            )

        has_premise = bool(response.get("has_premise", False))
        premise = str(response.get("premise", ""))
        verification_query = str(response.get("verification_query", ""))

        return PremiseResult(
            has_premise=has_premise,
            premise=premise,
            verification_query=verification_query,
            correction=None,
            source_citation=None,
        )

    except Exception as exc:
        logger.warning("scan_premise failed, returning safe fallback: %s", exc)
        return PremiseResult(
            has_premise=False, premise="", verification_query="",
            correction=None, source_citation=None,
        )


# ---------------------------------------------------------------------------
# Stage 2: verify_premise
# ---------------------------------------------------------------------------

_PREMISE_VERIFY_SCORE_THRESHOLD = 0.3


async def verify_premise(
    premise_result: PremiseResult,
    agency_filter: list[str] | None = None,
) -> PremiseResult:
    """Verify a flagged premise against real documents via targeted retrieval.

    Only called when premise_result.has_premise is True.  Runs retrieve()
    with the verification_query and checks whether the top result contradicts
    the stated premise (using a score threshold heuristic).

    Args:
        premise_result: The PremiseResult from scan_premise (must have
            has_premise=True).
        agency_filter: Optional agency filter to scope the verification
            retrieval.

    Returns:
        Updated PremiseResult.  If contradicting evidence found:
        correction and source_citation are populated.  Otherwise they
        remain None (premise unverifiable — proceed with answer).
    """
    if not premise_result.has_premise:
        return premise_result

    try:
        # retrieve() is synchronous — wrap in asyncio.to_thread
        results = await asyncio.to_thread(
            retrieve,
            premise_result.verification_query,
            agency_filter,
            5,  # top_k=5 for targeted verification
        )

        if not results:
            logger.info(
                "verify_premise: no results for verification_query=%r",
                premise_result.verification_query,
            )
            return premise_result

        top = results[0]
        if top.score >= _PREMISE_VERIFY_SCORE_THRESHOLD:
            # The verification_query searches for the thing the user claims
            # doesn't exist.  High-score hit = evidence contradicts the premise.
            # Extract a 1-sentence excerpt for the correction.
            text_excerpt = top.text.strip()
            # Take first sentence or first 200 chars, whichever is shorter
            first_sentence_end = text_excerpt.find(".")
            if 0 < first_sentence_end < 200:
                excerpt = text_excerpt[: first_sentence_end + 1]
            else:
                excerpt = text_excerpt[:200]

            return PremiseResult(
                has_premise=premise_result.has_premise,
                premise=premise_result.premise,
                verification_query=premise_result.verification_query,
                correction=excerpt,
                source_citation=top.citation,
            )

        logger.info(
            "verify_premise: top score %.3f < threshold %.3f, "
            "premise unverifiable",
            top.score,
            _PREMISE_VERIFY_SCORE_THRESHOLD,
        )
        return premise_result

    except Exception as exc:
        logger.warning("verify_premise failed: %s", exc)
        return premise_result
