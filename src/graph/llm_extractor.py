"""LLM-based relationship extraction using GPT-4.1-mini.

Replaces regex-based extraction for 5 relationship types:
CITES, IMPLEMENTS, DEFINED_BY, SUBJECT_TO, AMENDED_BY.

NEXT_SECTION remains code-based (positional chunk_index ordering).
Confidence is set to 0.9 for all LLM-extracted relationships (vs 1.0 for
rule-based) to distinguish them downstream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from openai import AsyncOpenAI, RateLimitError

from src.config import (
    LLM_CACHE_PATH,
    LLM_EXTRACT_MAX_CHUNK_CHARS,
    LLM_EXTRACT_MAX_CONCURRENT,
    LLM_EXTRACT_MODEL,
)
from src.graph.citation_index import normalize_citation, resolve_citation
from src.graph.extractor import Relationship, extract_next_section_edges

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLM_CONFIDENCE: float = 0.9

_REL_PRIORITY: list[str] = [
    "IMPLEMENTS",
    "SUBJECT_TO",
    "DEFINED_BY",
    "AMENDED_BY",
    "CITES",
]

_JSON_KEY_TO_REL: dict[str, str] = {
    "implements": "IMPLEMENTS",
    "subject_to": "SUBJECT_TO",
    "defined_by": "DEFINED_BY",
    "amended_by": "AMENDED_BY",
    "cites": "CITES",
}

# Maps chunk agency field values to the citation prefix used in citation_index.
# The chunk "agency" column may differ from the citation prefix (e.g., "Seattle DIR" → "DIR").
_AGENCY_TO_PREFIX: dict[str, str] = {
    "RCW": "RCW",
    "WAC": "WAC",
    "SMC": "SMC",
    "IBC": "IBC",
    "IBC-WA": "IBC",
    "DIR": "DIR",
    "SEATTLE DIR": "DIR",
    "SPU": "SPU",
}

_KNOWN_CITATION_PREFIXES: set[str] = set(_AGENCY_TO_PREFIX.values())

_SYSTEM_PROMPT = """\
You are a legal citation extractor for Washington State regulatory documents.
Given a regulatory text chunk, extract ALL explicit cross-references to other
legal sections and classify each into exactly one category.

Categories (in priority order — use the first that fits):

1. IMPLEMENTS: This section implements, is authorized by, or derives authority
   from the cited law. Signals: "Statutory Authority:", "implement the authority
   granted by", "pursuant to authority in", "Code Reference:", "Section Reference:".

2. SUBJECT_TO: This section is subject to, conditional upon, or must comply
   with the cited section. Signals: "subject to", "required under",
   "pursuant to", "in accordance with".

3. DEFINED_BY: A term in this section is defined by the cited section.
   Signals: "as defined in", "has the meaning set forth in", "see [citation] for definitions".

4. AMENDED_BY: This section supersedes, amends, or replaces the cited section.
   Signals: "Supersedes:", "as amended by", "amends", "replaces", "rescinds".

5. CITES: Any other cross-reference to another legal section not fitting categories 1-4.

Rules:
- Return ONLY citations that appear verbatim (or near-verbatim) in the text.
- Each citation must appear in exactly one category.
- Standard citation formats: "RCW X.Y.Z", "WAC X-Y-Z", "SMC X.Y.Z",
  "chapter X.Y RCW", "DR X-YYYY", "Executive Order XX-XX", "IBC X.Y",
  "SPU X.Y.Z", "Ord. XXXXXX".
- For comma-separated citation lists like "WAC 365-196-400, 365-196-401",
  always include the full agency prefix on EACH citation:
  "WAC 365-196-400", "WAC 365-196-401" (not just "365-196-401").
- Do NOT include the chunk's own citation in any category.

Return JSON with this exact structure:
{
  "implements": ["citation1", "citation2"],
  "subject_to": [],
  "defined_by": [],
  "amended_by": [],
  "cites": ["citation3"]
}"""


# ---------------------------------------------------------------------------
# Text sanitization + hallucination guard
# ---------------------------------------------------------------------------


def _sanitize_text(text: str) -> str:
    """Strip null bytes and non-printable control characters that break JSON payloads.

    Keeps newlines (\\n), carriage returns (\\r), and tabs (\\t) since those
    are valid in JSON strings and meaningful for legal text formatting.
    """
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


def _citation_in_text(citation: str, text: str) -> bool:
    """Return True if citation appears in text (whitespace-normalized, case-insensitive).

    Also accepts the citation if it starts with a known agency prefix and the
    bare number portion (without prefix) appears in the text.  This handles
    comma-separated lists like "WAC 365-196-400, 365-196-401" where the LLM
    correctly returns "WAC 365-196-401" but the text only has the bare number
    adjacent to the first full citation.
    """
    norm_cit = re.sub(r"\s+", " ", citation.strip()).lower()
    norm_text = re.sub(r"\s+", " ", text).lower()
    if norm_cit in norm_text:
        return True

    # Fallback: strip known agency prefix and check bare number
    for prefix in _KNOWN_CITATION_PREFIXES:
        if norm_cit.startswith(prefix.lower() + " "):
            bare = norm_cit[len(prefix) + 1:]
            if bare and bare in norm_text:
                return True
            break
    return False


_BARE_SECTION_RE = re.compile(
    r"^(?:Section|Subsection|Chapter)\s+",
    re.IGNORECASE,
)


def _expand_agency_prefix(raw_citation: str, source_agency: str) -> str:
    """Expand bare 'Section X.Y.Z', 'Chapter X.Y', or bare numbers to agency-prefixed form.

    When a chunk from a known agency contains a cross-reference like
    "Section 23.50.012 D" without an agency prefix, this function prepends the
    source chunk's agency so that ``resolve_citation()`` can find it in the
    citation_index (where keys are fully prefixed).

    Also handles bare numbers that the LLM may extract from comma-separated
    lists (e.g., "365-196-401" from "WAC 365-196-400, 365-196-401").

    Already-prefixed citations (e.g. "RCW 36.70A.681") pass through unchanged.
    Citations from unknown agencies pass through unchanged.
    Empty inputs return empty string.
    """
    if not raw_citation or not source_agency:
        return raw_citation

    # Map chunk agency field to citation prefix
    agency_upper = source_agency.strip().upper()
    citation_prefix = _AGENCY_TO_PREFIX.get(agency_upper)
    if citation_prefix is None:
        return raw_citation

    # If citation already starts with a known citation prefix, pass through
    cit_upper = raw_citation.strip().upper()
    for prefix in _KNOWN_CITATION_PREFIXES:
        if cit_upper.startswith(prefix + " "):
            return raw_citation

    # If citation starts with "Section " or "Chapter ", replace with agency prefix
    m = _BARE_SECTION_RE.match(raw_citation)
    if m:
        remainder = raw_citation[m.end():]
        return f"{citation_prefix} {remainder}"

    # Bare number detection: if the citation is just a number pattern
    # (no alphabetic prefix), prepend the source agency's citation prefix.
    # This handles comma-list extractions like "365-196-401" from WAC text.
    stripped = raw_citation.strip()
    if stripped and not _has_alpha_prefix(stripped):
        return f"{citation_prefix} {stripped}"

    return raw_citation


def _has_alpha_prefix(s: str) -> bool:
    """Return True if s starts with alphabetic characters (i.e., has an agency prefix)."""
    return bool(s) and s[0].isalpha()


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------


class LLMRelationshipExtractor:
    """Async LLM relationship extractor using GPT-4.1-mini.

    Args:
        model: OpenAI model name.
        max_concurrent: Max simultaneous API calls (semaphore size).
        max_retries: Retries on invalid JSON or rate limit errors.
        cache_path: Path to .jsonl cache file. When set, already-processed
            chunk IDs are skipped and new results are appended atomically.
            On restart, the cache is loaded and only unprocessed chunks are
            sent to the API. Pass None to disable caching.
    """

    def __init__(
        self,
        model: str = LLM_EXTRACT_MODEL,
        max_concurrent: int = LLM_EXTRACT_MAX_CONCURRENT,
        max_retries: int = 2,
        cache_path: Path | None = LLM_CACHE_PATH,
    ) -> None:
        self._model = model
        self._sem = asyncio.Semaphore(max_concurrent)
        self._max_retries = max_retries
        self._cache_path = cache_path
        self._cache: dict[str, list[dict[str, str]]] = {}
        self._cache_lock = asyncio.Lock()
        self._client: AsyncOpenAI | None = None
        self._stats: dict[str, int] = {
            "calls": 0,
            "hallucinations": 0,
            "failures": 0,
            "total_citations": 0,
            "cache_hits": 0,
        }

    def _load_cache(self) -> None:
        """Load existing cache from disk into self._cache."""
        if self._cache_path is None or not self._cache_path.exists():
            return
        loaded = 0
        with open(self._cache_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._cache[entry["chunk_id"]] = entry["results"]
                    loaded += 1
                except (json.JSONDecodeError, KeyError):
                    pass
        if loaded:
            logger.info("Loaded %d cached chunk results from %s", loaded, self._cache_path)

    async def _append_cache(self, chunk_id: str, results: list[dict[str, str]]) -> None:
        """Append one chunk's results to the cache file atomically."""
        if self._cache_path is None:
            return
        entry = json.dumps({"chunk_id": chunk_id, "results": results})
        async with self._cache_lock:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "a") as f:
                f.write(entry + "\n")

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    async def _extract_single(
        self,
        chunk_id: str,
        text: str,
        own_citation: str,
    ) -> list[dict[str, str]]:
        """One LLM call for one chunk.

        Returns:
            List of {"raw_citation": str, "rel_type": str} dicts for
            verified (non-hallucinated) citations only.
        """
        clean_text = _sanitize_text(text)
        truncated = clean_text[:LLM_EXTRACT_MAX_CHUNK_CHARS]
        user_msg = (
            f"Chunk citation: {own_citation or '(unknown)'}\n\n"
            f"Text:\n{truncated}"
        )

        raw_json: dict[str, Any] = {}
        async with self._sem:
            self._stats["calls"] += 1
            for attempt in range(1 + self._max_retries):
                try:
                    response = await self.client.chat.completions.create(
                        model=self._model,
                        response_format={"type": "json_object"},
                        temperature=0.0,
                        messages=[
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                    )
                    raw_json = json.loads(response.choices[0].message.content)
                    break
                except RateLimitError:
                    wait = 2 ** attempt
                    logger.warning(
                        "Rate limit on chunk %s, waiting %ds (attempt %d)",
                        chunk_id, wait, attempt + 1,
                    )
                    await asyncio.sleep(wait)
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning(
                        "LLM extraction failed for chunk %s attempt %d: %s",
                        chunk_id, attempt + 1, exc,
                    )
            else:
                self._stats["failures"] += 1
                return []

        # Flatten JSON → (citation, rel_type) with priority dedup
        seen_citations: set[str] = set()
        results: list[dict[str, str]] = []

        for json_key in ["implements", "subject_to", "defined_by", "amended_by", "cites"]:
            rel_type = _JSON_KEY_TO_REL[json_key]
            citations = raw_json.get(json_key, [])
            if not isinstance(citations, list):
                continue

            for cit in citations:
                if not isinstance(cit, str) or not cit.strip():
                    continue
                norm = normalize_citation(cit)
                # Skip own citation and duplicates (higher priority wins)
                if own_citation and norm == normalize_citation(own_citation):
                    continue
                if norm in seen_citations:
                    continue
                # Hallucination guard
                if not _citation_in_text(cit, text):
                    logger.debug(
                        "Hallucination filtered: %r not in chunk %s", cit, chunk_id
                    )
                    self._stats["hallucinations"] += 1
                    continue

                seen_citations.add(norm)
                self._stats["total_citations"] += 1
                results.append({"raw_citation": cit, "rel_type": rel_type})

        return results

    async def extract_all(
        self,
        chunks_df: pd.DataFrame,
        citation_index: dict[str, str],
        chapter_index: dict[str, list[str]],
    ) -> tuple[list[Relationship], list[dict]]:
        """LLM-extract relationships for all chunks, then resolve citations.

        Chunks already present in the cache are skipped (no API call).
        New results are appended to the cache as they complete so progress
        is preserved across crashes/restarts.

        Returns:
            Tuple of (resolved_relationships, unresolved_dicts) — same
            format as ``extract_all_relationships()`` in extractor.py.
        """
        # Load cache from disk
        self._load_cache()

        rows = list(chunks_df.iterrows())
        total = len(rows)
        cache_hits = sum(1 for _, row in rows if str(row["id"]) in self._cache)
        logger.info(
            "Dispatching LLM extraction for %d chunks (%d cached, %d to process)...",
            total, cache_hits, total - cache_hits,
        )

        async def _extract_with_cache(chunk_id: str, text: str, own_citation: str) -> list[dict[str, str]]:
            if chunk_id in self._cache:
                self._stats["cache_hits"] += 1
                return self._cache[chunk_id]
            results = await self._extract_single(chunk_id, text, own_citation)
            await self._append_cache(chunk_id, results)
            return results

        tasks = [
            _extract_with_cache(
                chunk_id=str(row["id"]),
                text=str(row.get("text", "") or ""),
                own_citation=str(row.get("citation", "") or ""),
            )
            for _, row in rows
        ]

        results_per_chunk = await asyncio.gather(*tasks)
        logger.info(
            "LLM extraction complete. Calls=%d, cache_hits=%d, hallucinations=%d, failures=%d",
            self._stats["calls"],
            self._stats["cache_hits"],
            self._stats["hallucinations"],
            self._stats["failures"],
        )

        # Build Relationship objects via citation resolution
        all_relationships: list[Relationship] = []

        for (_, row), chunk_results in zip(rows, results_per_chunk):
            chunk_id = str(row["id"])
            source_agency = str(row.get("agency", "") or "").strip()
            for item in chunk_results:
                raw_cit = item["raw_citation"]
                expanded_cit = _expand_agency_prefix(raw_cit, source_agency)
                rel_type = item["rel_type"]
                target_id = resolve_citation(expanded_cit, citation_index, chapter_index, allow_chapter_fallback=False) or ""
                rel = Relationship(
                    source_id=chunk_id,
                    target_id=target_id,
                    rel_type=rel_type,
                    confidence=LLM_CONFIDENCE,
                    raw_citation=expanded_cit,
                    source="llm",
                )
                if target_id != chunk_id:  # no self-edges
                    all_relationships.append(rel)

        # NEXT_SECTION stays code-based
        next_section = extract_next_section_edges(chunks_df)
        all_relationships.extend(next_section)

        # Dedup by (source_id, target_id, rel_type)
        seen_triples: set[tuple[str, str, str]] = set()
        deduped: list[Relationship] = []
        for rel in all_relationships:
            key = (rel.source_id, rel.target_id, rel.rel_type)
            if key not in seen_triples:
                seen_triples.add(key)
                deduped.append(rel)

        # Collect unresolved
        unresolved: list[dict] = [
            {
                "source_chunk_id": rel.source_id,
                "raw_citation": rel.raw_citation,
                "relationship_type": rel.rel_type,
                "reason": "no chunk found with matching citation",
            }
            for rel in deduped
            if rel.target_id == "" and rel.rel_type != "NEXT_SECTION"
        ]

        # Return only resolved edges (+ NEXT_SECTION which has no target_id check)
        resolved = [
            r for r in deduped
            if r.target_id != "" or r.rel_type == "NEXT_SECTION"
        ]

        logger.info(
            "Resolved %d relationships (%d unresolved, %d NEXT_SECTION)",
            len(resolved),
            len(unresolved),
            sum(1 for r in resolved if r.rel_type == "NEXT_SECTION"),
        )
        return resolved, unresolved


# ---------------------------------------------------------------------------
# Sync entry point
# ---------------------------------------------------------------------------


def extract_relationships_llm(
    chunks_df: pd.DataFrame,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
    model: str = LLM_EXTRACT_MODEL,
    max_concurrent: int = LLM_EXTRACT_MAX_CONCURRENT,
    cache_path: Path | None = LLM_CACHE_PATH,
) -> tuple[list[Relationship], list[dict]]:
    """Sync wrapper for LLM-based relationship extraction.

    Drop-in replacement for ``extract_all_relationships()`` — same
    signature and return type.

    Args:
        chunks_df: DataFrame with id, text, agency, citation, filename,
            chunk_index columns.
        citation_index: ``{normalized_citation -> chunk_id}`` mapping.
        chapter_index: ``{chapter_prefix -> [chunk_ids]}`` mapping.
        model: OpenAI model to use.
        max_concurrent: Max simultaneous API calls.
        cache_path: Path to .jsonl cache file for resume support. Pass
            None to disable caching.

    Returns:
        Tuple of (resolved_relationships, unresolved_dicts).
    """
    extractor = LLMRelationshipExtractor(
        model=model, max_concurrent=max_concurrent, cache_path=cache_path
    )
    result = asyncio.run(
        extractor.extract_all(chunks_df, citation_index, chapter_index)
    )
    stats = extractor.get_stats()
    total = stats["total_citations"] + stats["hallucinations"]
    halluc_pct = (100 * stats["hallucinations"] / total) if total > 0 else 0.0
    logger.info(
        "LLM extraction stats: calls=%d, citations_found=%d, "
        "hallucinations_filtered=%d (%.1f%%), failures=%d",
        stats["calls"],
        stats["total_citations"],
        stats["hallucinations"],
        halluc_pct,
        stats["failures"],
    )
    return result
