"""CONFLICTS_WITH candidate generation and GPT-4.1 mini adjudicator.

Two-pass candidate generation per D-03:
  - Pass A: Same-authority IMPLEMENTS clustering (different agencies
    implementing the same RCW produce candidate conflict pairs).
  - Pass C: Cross-agency vector similarity >= threshold in LanceDB,
    restricted to SMC/WAC/RCW agency pairs only.

The adjudicator sends each candidate pair to GPT-4.1 mini for conflict
detection with structured JSON output.

Functions:
    generate_conflict_candidates: Two-pass candidate pair generation.
    adjudicate_conflict: Single-pair LLM conflict detection.
    adjudicate_conflicts: Batch adjudication of all candidate pairs.

Classes:
    ConflictResult: Dataclass holding adjudication output for one pair.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from openai import OpenAI

from src.graph.extractor import Relationship

logger = logging.getLogger(__name__)

# System prompt for the conflict adjudicator (from RESEARCH.md)
_SYSTEM_PROMPT = (
    "You are a legal analyst specializing in Washington State regulatory law. "
    "Determine if two regulatory sections create CONTRADICTORY requirements. "
    "CONTRADICTORY = one says X is required, other says X is prohibited, "
    "or they impose mutually exclusive requirements on the same subject. "
    "COMPLEMENTARY = one authorizes, other implements; or one general, "
    "other specific; or both apply and local is stricter (allowed in WA). "
    'Return JSON: {"conflict": bool, "description": str, '
    '"confidence": float (0.0-1.0), "resolution": str}'
)

# Required keys in the LLM JSON response
_REQUIRED_KEYS = {"conflict", "description", "confidence", "resolution"}


@dataclass
class ConflictResult:
    """Result of a single conflict adjudication between two chunks.

    Attributes:
        source_id: First chunk ID in the pair.
        target_id: Second chunk ID in the pair.
        conflict: Whether a true conflict was detected.
        description: Human-readable description of the conflict (or lack thereof).
        confidence: Adjudicator confidence score (0.0-1.0).
        resolution: Suggested resolution or empty string.
    """

    source_id: str
    target_id: str
    conflict: bool
    description: str
    confidence: float
    resolution: str


def generate_conflict_candidates(
    relationships: list[Relationship],
    lancedb_table,
    chunk_agencies: dict[str, str],
    agency_filter: set[str] | None = None,
    sim_threshold: float = 0.90,
) -> list[tuple[str, str]]:
    """Generate CONFLICTS_WITH candidate pairs via two passes.

    Pass A -- Same-authority clustering (per D-03):
        Group IMPLEMENTS edges by target (the RCW being implemented). If
        two or more chunks from *different* agencies implement the same
        RCW, they form candidate conflict pairs.

    Pass C -- Cross-agency vector similarity (per D-03):
        For each chunk in an eligible agency, search LanceDB for
        cross-agency matches with cosine similarity >= ``sim_threshold``.
        Restricted to ``agency_filter`` pairs only.

    The union of both passes is deduplicated before returning.

    Args:
        relationships: List of extracted Relationship objects (needs
            IMPLEMENTS edges for Pass A).
        lancedb_table: LanceDB table object for vector similarity search
            in Pass C.  May be ``None`` to skip Pass C.
        chunk_agencies: Mapping of ``chunk_id -> agency`` name.
        agency_filter: Set of agency names to include.  Defaults to
            ``{"SMC", "WAC", "RCW"}``.
        sim_threshold: Minimum cosine similarity for Pass C candidates.

    Returns:
        List of ``(chunk_id_a, chunk_id_b)`` tuples (sorted within each
        pair for consistent deduplication).
    """
    if agency_filter is None:
        agency_filter = {"SMC", "WAC", "RCW"}

    candidates: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------
    # Pass A: Same-authority IMPLEMENTS clustering
    # ------------------------------------------------------------------
    rcw_to_implementors: dict[str, list[str]] = {}
    for rel in relationships:
        if rel.rel_type == "IMPLEMENTS" and rel.target_id:
            rcw_to_implementors.setdefault(rel.target_id, []).append(
                rel.source_id
            )

    for rcw_id, impl_ids in rcw_to_implementors.items():
        # Group implementors by agency
        by_agency: dict[str, list[str]] = {}
        for impl_id in impl_ids:
            agency = chunk_agencies.get(impl_id, "")
            if agency in agency_filter:
                by_agency.setdefault(agency, []).append(impl_id)
        # Cross-product of different agencies
        agencies = list(by_agency.keys())
        for i in range(len(agencies)):
            for j in range(i + 1, len(agencies)):
                for id_a in by_agency[agencies[i]]:
                    for id_b in by_agency[agencies[j]]:
                        pair = tuple(sorted([id_a, id_b]))
                        candidates.add(pair)

    logger.info("Pass A generated %d candidate pairs", len(candidates))

    # ------------------------------------------------------------------
    # Pass C: Cross-agency vector similarity
    # ------------------------------------------------------------------
    if lancedb_table is not None:
        pass_c_count = 0
        df = lancedb_table.to_pandas()
        # Filter to eligible agencies only
        filtered = df[df["agency"].isin(agency_filter)]

        for _, chunk in filtered.iterrows():
            chunk_agency = chunk["agency"]
            chunk_id = chunk["id"]

            try:
                results = (
                    lancedb_table.search(chunk["embedding"])
                    .distance_type("cosine")
                    .where(f"agency != '{chunk_agency}'")
                    .limit(5)
                    .to_pandas()
                )
            except Exception as exc:
                logger.warning(
                    "Pass C search failed for %s: %s", chunk_id, exc
                )
                continue

            for _, match in results.iterrows():
                match_agency = match["agency"]
                if match_agency not in agency_filter:
                    continue
                sim = 1 - match["_distance"]  # cosine distance -> similarity
                if sim >= sim_threshold:
                    pair = tuple(sorted([chunk_id, match["id"]]))
                    if pair not in candidates:
                        pass_c_count += 1
                    candidates.add(pair)

        logger.info("Pass C added %d new candidate pairs", pass_c_count)

    logger.info("Total deduplicated candidates: %d", len(candidates))
    return list(candidates)


def adjudicate_conflict(
    client: OpenAI,
    text_a: str,
    agency_a: str,
    text_b: str,
    agency_b: str,
    max_retries: int = 2,
) -> dict:
    """Adjudicate a single candidate pair for conflict via GPT-4.1 mini.

    Sends both section texts (truncated to 500 chars each) to the LLM
    and expects a JSON response with keys: conflict, description,
    confidence, resolution.

    Args:
        client: OpenAI client instance.
        text_a: Text of the first section.
        agency_a: Agency of the first section.
        text_b: Text of the second section.
        agency_b: Agency of the second section.
        max_retries: Maximum number of retries on invalid JSON.

    Returns:
        Dict with keys: conflict (bool), description (str),
        confidence (float), resolution (str).  On total failure returns
        a safe default with conflict=False.
    """
    user_message = (
        f"Section A (from {agency_a}):\n{text_a[:500]}\n\n"
        f"Section B (from {agency_b}):\n{text_b[:500]}"
    )

    for attempt in range(1 + max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)

            # Validate required keys
            if _REQUIRED_KEYS.issubset(result.keys()):
                return result

            logger.warning(
                "Attempt %d: Missing keys in response: %s",
                attempt + 1,
                _REQUIRED_KEYS - result.keys(),
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(
                "Attempt %d: Adjudication failed: %s", attempt + 1, exc
            )

    # All retries exhausted -- return safe default
    logger.error("All %d attempts failed for adjudication", 1 + max_retries)
    return {
        "conflict": False,
        "description": "adjudication failed",
        "confidence": 0.0,
        "resolution": "",
    }


def adjudicate_conflicts(
    candidates: list[tuple[str, str]],
    chunks_df,
    client: OpenAI,
) -> list[ConflictResult]:
    """Adjudicate all candidate pairs and return ConflictResult objects.

    For each pair, looks up text and agency from ``chunks_df``, calls
    ``adjudicate_conflict``, and wraps the result in a ``ConflictResult``.

    Args:
        candidates: List of ``(chunk_id_a, chunk_id_b)`` pairs.
        chunks_df: DataFrame with ``id``, ``text``, ``agency`` columns.
        client: OpenAI client instance.

    Returns:
        List of ``ConflictResult`` objects (both conflict=True and
        conflict=False -- caller decides how to filter).
    """
    # Build lookup dicts for fast access
    id_to_text: dict[str, str] = dict(zip(chunks_df["id"], chunks_df["text"]))
    id_to_agency: dict[str, str] = dict(
        zip(chunks_df["id"], chunks_df["agency"])
    )

    results: list[ConflictResult] = []
    total = len(candidates)

    for i, (id_a, id_b) in enumerate(candidates):
        text_a = id_to_text.get(id_a, "")
        text_b = id_to_text.get(id_b, "")
        agency_a = id_to_agency.get(id_a, "Unknown")
        agency_b = id_to_agency.get(id_b, "Unknown")

        if not text_a or not text_b:
            logger.warning(
                "Skipping pair (%s, %s): missing text", id_a, id_b
            )
            continue

        adjudication = adjudicate_conflict(
            client=client,
            text_a=text_a,
            agency_a=agency_a,
            text_b=text_b,
            agency_b=agency_b,
        )

        results.append(
            ConflictResult(
                source_id=id_a,
                target_id=id_b,
                conflict=adjudication["conflict"],
                description=adjudication["description"],
                confidence=adjudication["confidence"],
                resolution=adjudication["resolution"],
            )
        )

        if (i + 1) % 10 == 0:
            logger.info("Adjudicated %d/%d pairs...", i + 1, total)

    logger.info("Adjudication complete: %d/%d pairs processed", len(results), total)
    return results
