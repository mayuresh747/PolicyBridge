"""Citation index builder for the Seattle Regulatory RAG knowledge graph.

Builds a lookup dictionary mapping normalized citation strings to chunk IDs,
enabling cross-reference resolution during relationship extraction.

Also builds a chapter-level index for resolving chapter-level citations
(e.g., "chapter 36.70A RCW") to all chunks within that chapter.

Functions:
    normalize_citation: Collapse whitespace and strip a citation string.
    build_citation_index: Scan all LanceDB chunks, build exact + chapter indexes.
    resolve_citation: Look up a raw citation string, return chunk_id or None.
"""

from __future__ import annotations

import re
from typing import Optional


def normalize_citation(citation: str) -> str:
    """Normalize a citation string for consistent lookup.

    Collapses multiple whitespace characters to a single space and strips
    leading/trailing whitespace.

    Examples:
        >>> normalize_citation("RCW  36.70A.681")
        'RCW 36.70A.681'
        >>> normalize_citation("  WAC 365-196-410  ")
        'WAC 365-196-410'
    """
    return re.sub(r"\s+", " ", citation.strip())


def build_citation_index(
    lancedb_table,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Scan all chunks in a LanceDB table and build citation lookup indexes.

    Args:
        lancedb_table: A LanceDB table object (or mock) that supports
            ``.to_pandas()`` returning a DataFrame with ``id`` and ``citation``
            columns.

    Returns:
        A 2-tuple of:
        - ``citation_index``: ``{normalized_citation -> chunk_id}`` for exact
          lookups.
        - ``chapter_index``: ``{chapter_prefix -> [chunk_ids]}`` for
          chapter-level resolution. Chapter prefix is derived by dropping the
          last segment of the citation:
          - WAC (hyphen-separated): ``"WAC 365-196-410"`` -> ``"WAC 365-196"``
          - RCW/SMC (dot-separated): ``"RCW 36.70A.681"`` -> ``"RCW 36.70A"``
    """
    df = lancedb_table.to_pandas()
    citation_index: dict[str, str] = {}
    chapter_index: dict[str, list[str]] = {}

    for _, row in df.iterrows():
        raw_citation = row.get("citation", "")
        if not raw_citation or not str(raw_citation).strip():
            continue

        normalized = normalize_citation(str(raw_citation))
        chunk_id = row["id"]
        citation_index[normalized] = chunk_id

        # Build chapter-level index
        chapter_prefix = _extract_chapter_prefix(normalized)
        if chapter_prefix:
            chapter_index.setdefault(chapter_prefix, []).append(chunk_id)

    return citation_index, chapter_index


def _extract_chapter_prefix(normalized_citation: str) -> str | None:
    """Extract the chapter-level prefix from a normalized citation.

    Rules:
    - WAC citations (contain hyphens after the agency prefix):
      ``"WAC 365-196-410"`` -> ``"WAC 365-196"`` (drop last hyphen segment)
    - RCW/SMC/IBC citations (contain dots after the agency prefix):
      ``"RCW 36.70A.681"`` -> ``"RCW 36.70A"`` (drop last dot segment)

    Returns:
        The chapter prefix string, or None if the citation format is
        unrecognized.
    """
    parts = normalized_citation.split(" ", 1)
    if len(parts) != 2:
        return None

    agency_prefix, number_part = parts

    # WAC uses hyphens: "365-196-410" -> "365-196"
    if "-" in number_part and agency_prefix.upper() == "WAC":
        chapter = number_part.rsplit("-", 1)[0]
        return f"{agency_prefix} {chapter}"

    # RCW, SMC, IBC use dots: "36.70A.681" -> "36.70A"
    if "." in number_part:
        chapter = number_part.rsplit(".", 1)[0]
        return f"{agency_prefix} {chapter}"

    return None


def _is_section_level(normalized_citation: str) -> bool:
    """Return True if the citation targets a specific section (not a chapter).

    Section-level citations should NOT fall back to chapter-level resolution
    because doing so creates false edges (e.g., "RCW 62A.9A-709" would
    incorrectly resolve to the first chunk in chapter "RCW 62A.9A").

    Rules:
    - WAC: 3+ hyphen-separated segments means section-level
      (e.g., ``"WAC 365-196-410"`` is section; ``"WAC 365-196"`` is chapter)
    - RCW/SMC: 3+ dot-separated segments means section-level
      (e.g., ``"RCW 36.70A.681"`` is section; ``"RCW 36.70A"`` is chapter)
    - RCW-style with hyphen after chapter part means section-level
      (e.g., ``"RCW 62A.9A-709"`` has a hyphen section suffix)

    Returns:
        True if citation is section-level (no chapter fallback allowed),
        False if citation is chapter-level (fallback OK).
    """
    parts = normalized_citation.split(" ", 1)
    if len(parts) != 2:
        return False

    agency, number = parts

    # WAC: count hyphen-separated segments
    if agency.upper() == "WAC":
        segments = number.split("-")
        return len(segments) >= 3

    # RCW/SMC/IBC: check for 3+ dot segments OR a hyphen after the chapter part
    if "." in number:
        dot_segments = number.split(".")
        if len(dot_segments) >= 3:
            return True
        # Check for hyphen section suffix (e.g., "62A.9A-709")
        if "-" in number:
            return True

    return False


def resolve_citation(
    raw_citation: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
    allow_chapter_fallback: bool = True,
) -> Optional[str]:
    """Resolve a raw citation string to a chunk ID.

    First attempts an exact match in the citation index.  If no exact match
    is found, tries stripping subsection markers (e.g., ``(a)(1)``).  For
    bare ``Section X.Y.Z`` references (common in SMC text), tries an
    ``SMC X.Y.Z`` alias lookup.  If the citation is chapter-level, looks up
    in the chapter index and returns the first match (if any).  Section-level
    citations that cannot be resolved exactly return None (retry queue).

    Args:
        raw_citation: The citation string extracted from chunk text
            (e.g., ``"RCW 36.70A.681"``).
        citation_index: Exact-match lookup from ``build_citation_index()``.
        chapter_index: Chapter-level lookup from ``build_citation_index()``.
        allow_chapter_fallback: If False, skip chapter-index fallback entirely.
            The LLM extractor passes False to prevent chapter-level references
            (like "SMC 23.76") from false-resolving to the first chunk in
            that chapter. Defaults to True for backward compatibility.

    Returns:
        The chunk ID if found, or ``None`` if the citation cannot be resolved.
    """
    normalized = normalize_citation(raw_citation)

    # Try exact match first
    exact = citation_index.get(normalized)
    if exact is not None:
        return exact

    # Try stripping trailing subsection markers iteratively
    # e.g., "RCW 62A.9A-501(a)(1)" -> try "RCW 62A.9A-501(a)" -> try "RCW 62A.9A-501"
    stripped = normalized
    while re.search(r"\([a-z0-9]+\)$", stripped, re.IGNORECASE):
        stripped = re.sub(r"\([a-z0-9]+\)$", "", stripped, flags=re.IGNORECASE).rstrip()
        match = citation_index.get(stripped)
        if match is not None:
            return match

    # Try "Section X.Y.Z" -> "SMC X.Y.Z" alias resolution.
    # SMC code text uses bare "Section" references (e.g., "Section 23.45.502")
    # but the citation index stores them under "SMC 23.45.502".
    if normalized.startswith("Section "):
        smc_alias = "SMC " + normalized[len("Section "):]
        smc_match = citation_index.get(smc_alias)
        if smc_match is not None:
            return smc_match
        # Also try stripping subsection markers on the SMC alias
        smc_stripped = smc_alias
        while re.search(r"\([a-z0-9]+\)$", smc_stripped, re.IGNORECASE):
            smc_stripped = re.sub(
                r"\([a-z0-9]+\)$", "", smc_stripped, flags=re.IGNORECASE
            ).rstrip()
            smc_match = citation_index.get(smc_stripped)
            if smc_match is not None:
                return smc_match

    # If the citation is section-level, do NOT fall back to chapter index.
    # Section-level citations that miss exact match go to the retry queue.
    if _is_section_level(normalized):
        return None

    if allow_chapter_fallback:
        # Try the normalized citation itself as a chapter-level key
        # e.g., "RCW 76.09" is itself a chapter prefix in chapter_index
        if normalized in chapter_index:
            matches = chapter_index[normalized]
            if matches:
                return matches[0]

        # Try chapter-level match for chapter-level citations
        # e.g., "chapter 36.70A RCW" might resolve via chapter_index
        chapter_prefix = _extract_chapter_prefix(normalized)
        if chapter_prefix and chapter_prefix in chapter_index:
            matches = chapter_index[chapter_prefix]
            if matches:
                return matches[0]

    return None
