"""Rule-based relationship extraction for the Seattle Regulatory RAG knowledge graph.

NOTE: This module contains the legacy regex-based extractors for 5 cross-chunk
relationship types. The primary extractor is now ``llm_extractor.py``
(GPT-4.1-mini), used by default in ``scripts/run_graph.py``.

This module is retained for:
- A/B comparison via the ``--use-regex`` flag in ``run_graph.py``
- ``extract_next_section_edges`` — still code-based (positional ordering)
- ``extract_hierarchy`` — still code-based (Agency → Document → Chunk)

Extracts 6 deterministic relationship types from chunk text:
- CITES: generic cross-reference to another section
- IMPLEMENTS: WAC/SMC/DIR implementing an RCW authority
- DEFINED_BY: term definition reference
- SUBJECT_TO: conditional dependency on another section
- AMENDED_BY: supersession or amendment reference
- NEXT_SECTION: sequential ordering within a document

Functions:
    extract_all_relationships: Regex-based entry point (legacy).
    extract_next_section_edges: NEXT_SECTION edges from chunk_index + filename.
    extract_hierarchy: Agency → Document → Chunk hierarchy nodes and edges.

The CITES extraction reuses ``extract_citations()`` from ``src.chunkers.base``
to avoid duplicating citation regex patterns (per D-02).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.chunkers.base import extract_citations
from src.config import AUTHORITY_LEVELS
from src.graph.citation_index import normalize_citation, resolve_citation


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Relationship:
    """A single extracted relationship between two chunks.

    Attributes:
        source_id: The chunk ID of the source (where the reference appears).
        target_id: The resolved chunk ID of the target, or ``""`` if unresolved.
        rel_type: One of CITES, IMPLEMENTS, DEFINED_BY, SUBJECT_TO,
            AMENDED_BY, NEXT_SECTION.
        confidence: 1.0 for all rule-based extractions.
        raw_citation: The original citation string before resolution.
        source: How the relationship was detected: ``"regex"`` or ``"chunk_index"``.
    """

    source_id: str
    target_id: str
    rel_type: str
    confidence: float
    raw_citation: str
    source: str


# ---------------------------------------------------------------------------
# Regex patterns for relationship extraction
# (from RESEARCH.md, validated against ARCHITECTURE.md)
# ---------------------------------------------------------------------------

IMPLEMENTS_PATTERNS = [
    re.compile(r"\[Statutory Authority:\s*(.*?)\]", re.DOTALL),
    re.compile(
        r"implement.*?(?:authority granted.*?by\s+)?"
        r"((?:RCW|chapter[\s\d.]+RCW)[\s\d.A-Za-z]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"purpose of this chapter is to implement.*?"
        r"((?:chapter[\s\d.]+RCW|RCW[\s\d.A-Za-z]+))",
        re.IGNORECASE,
    ),
    re.compile(r"Code.*?Reference:\s*(.+?)(?:\n|$)"),  # DIR header
]

SUBJECT_TO_PATTERNS = [
    re.compile(
        r"(?:shall be\s+)?subject to (?:the provisions of\s+)?"
        r"(?:Section\s+)?((?:RCW|WAC|SMC)\s+[\d.\-A-Za-z]+)"
    ),
    re.compile(r"as subject to:?\s+((?:RCW|WAC)\s+[\d.,\s]+)"),
    re.compile(r"required.*?under\s+(RCW\s+[\d.A-Za-z]+)"),
    re.compile(
        r"(?:pursuant to|in accordance with)\s+((?:RCW|WAC|SMC)\s+[\d.\-A-Za-z]+)"
    ),
]

DEFINED_BY_PATTERNS = [
    re.compile(
        r"(?:as\s+)?defined\s+in\s+((?:RCW|WAC|SMC)\s+[\d.\-A-Za-z]+)"
    ),
    re.compile(r"has the meaning set forth in\s+(?:Section\s+)?([\d.]+)"),
    re.compile(r"as used in this chapter.*?see\s+(WAC\s+[\d\-]+)"),
]

AMENDED_BY_PATTERNS = [
    re.compile(r"Supersedes:\s*(.+?)(?:\n|$)"),
    re.compile(
        r"(?:as amended by|amends)\s+((?:RCW|WAC|SMC|Ord\.)\s+[\d.\-]+)"
    ),
    re.compile(
        r"(?:supersedes|replaces|rescinds)\s+(?:Executive Order|EO)\s+(\d{2}-\d{2})"
    ),
]


# ---------------------------------------------------------------------------
# Internal extraction helpers
# ---------------------------------------------------------------------------


def _citations_from_text(text: str) -> list[str]:
    """Extract citation strings from arbitrary text using base.py patterns.

    This is a thin wrapper around ``extract_citations()`` that returns the
    full match strings (e.g., ``"RCW 36.70A.681"``).
    """
    return extract_citations(text)


def _make_relationship(
    source_id: str,
    raw_citation: str,
    rel_type: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> Relationship:
    """Create a Relationship, resolving the target via the citation index."""
    target_id = resolve_citation(raw_citation, citation_index, chapter_index)
    return Relationship(
        source_id=source_id,
        target_id=target_id or "",
        rel_type=rel_type,
        confidence=1.0,
        raw_citation=raw_citation,
        source="regex",
    )


CHAPTER_RCW_RE = re.compile(
    r"chapters?\s+([\d.]+[A-Z]?(?:\s+and\s+[\d.]+[A-Z]?)*)\s+RCW",
    re.IGNORECASE,
)


def _extract_implements(
    text: str,
    source_id: str,
    agency: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> list[Relationship]:
    """Extract IMPLEMENTS relationships from chunk text.

    - WAC: Match Statutory Authority blocks and extract ALL cited RCWs.
    - SMC: Match 'implement the authority granted by' patterns.
    - DIR: Match 'Code/Section Reference:' headers.
    - All agencies: Match 'chapter(s) X.Y RCW' suffix format.
    """
    results: list[Relationship] = []
    seen_citations: set[str] = set()

    if agency == "WAC":
        # Pattern 0: [Statutory Authority: RCW ..., RCW ...]
        match = IMPLEMENTS_PATTERNS[0].search(text)
        if match:
            authority_block = match.group(1)
            citations = _citations_from_text(authority_block)
            for cit in citations:
                normalized = normalize_citation(cit)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, cit, "IMPLEMENTS",
                            citation_index, chapter_index,
                        )
                    )
    elif agency == "SMC":
        # Patterns 1 and 2: "implement...authority granted by RCW"
        for pattern in IMPLEMENTS_PATTERNS[1:3]:
            for match in pattern.finditer(text):
                captured = match.group(1)
                citations = _citations_from_text(captured)
                if not citations:
                    # The captured text itself might be a citation
                    citations = _citations_from_text(match.group(0))
                for cit in citations:
                    normalized = normalize_citation(cit)
                    if normalized not in seen_citations:
                        seen_citations.add(normalized)
                        results.append(
                            _make_relationship(
                                source_id, cit, "IMPLEMENTS",
                                citation_index, chapter_index,
                            )
                        )
    elif agency == "Seattle DIR":
        # Pattern 3: Code/Section Reference header
        match = IMPLEMENTS_PATTERNS[3].search(text)
        if match:
            captured = match.group(1)
            citations = _citations_from_text(captured)
            for cit in citations:
                normalized = normalize_citation(cit)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, cit, "IMPLEMENTS",
                            citation_index, chapter_index,
                        )
                    )

    # For WAC, SMC, and Seattle DIR: match "chapter(s) X.Y RCW" suffix format
    if agency in ("WAC", "SMC", "Seattle DIR"):
        for m in CHAPTER_RCW_RE.finditer(text):
            chapter_group = m.group(1)
            chapter_numbers = re.split(r"\s+and\s+", chapter_group, flags=re.IGNORECASE)
            for ch_num in chapter_numbers:
                ch_num = ch_num.strip()
                if not ch_num:
                    continue
                rcw_citation = f"RCW {ch_num}"
                normalized = normalize_citation(rcw_citation)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, rcw_citation, "IMPLEMENTS",
                            citation_index, chapter_index,
                        )
                    )

    return results


def _extract_subject_to(
    text: str,
    source_id: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> list[Relationship]:
    """Extract SUBJECT_TO relationships from chunk text."""
    results: list[Relationship] = []
    seen_citations: set[str] = set()

    for pattern in SUBJECT_TO_PATTERNS:
        for match in pattern.finditer(text):
            captured = match.group(1)
            citations = _citations_from_text(captured)
            if not citations:
                # Try the full match
                citations = _citations_from_text(match.group(0))
            for cit in citations:
                normalized = normalize_citation(cit)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, cit, "SUBJECT_TO",
                            citation_index, chapter_index,
                        )
                    )

    return results


def _extract_defined_by(
    text: str,
    source_id: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> list[Relationship]:
    """Extract DEFINED_BY relationships from chunk text."""
    results: list[Relationship] = []
    seen_citations: set[str] = set()

    for pattern in DEFINED_BY_PATTERNS:
        for match in pattern.finditer(text):
            captured = match.group(1)
            citations = _citations_from_text(captured)
            if not citations:
                citations = _citations_from_text(match.group(0))
            for cit in citations:
                normalized = normalize_citation(cit)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, cit, "DEFINED_BY",
                            citation_index, chapter_index,
                        )
                    )

    return results


def _extract_amended_by(
    text: str,
    source_id: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> list[Relationship]:
    """Extract AMENDED_BY relationships from chunk text."""
    results: list[Relationship] = []
    seen_citations: set[str] = set()

    for pattern in AMENDED_BY_PATTERNS:
        for match in pattern.finditer(text):
            captured = match.group(1)
            citations = _citations_from_text(captured)
            if not citations:
                citations = _citations_from_text(match.group(0))
            for cit in citations:
                normalized = normalize_citation(cit)
                if normalized not in seen_citations:
                    seen_citations.add(normalized)
                    results.append(
                        _make_relationship(
                            source_id, cit, "AMENDED_BY",
                            citation_index, chapter_index,
                        )
                    )

    return results


def _extract_cites(
    text: str,
    source_id: str,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
    already_extracted: set[str],
) -> list[Relationship]:
    """Extract CITES relationships from chunk text.

    Uses ``extract_citations()`` from ``src.chunkers.base`` (per D-02).
    Deduplicates against ``already_extracted`` -- if a citation already
    produced an IMPLEMENTS, DEFINED_BY, SUBJECT_TO, or AMENDED_BY edge,
    it is not duplicated as a CITES edge.

    Args:
        already_extracted: Set of normalized citation strings that have
            already been extracted as more specific relationship types.
    """
    results: list[Relationship] = []
    citations = _citations_from_text(text)

    for cit in citations:
        normalized = normalize_citation(cit)
        if normalized in already_extracted:
            continue
        already_extracted.add(normalized)
        results.append(
            _make_relationship(
                source_id, cit, "CITES",
                citation_index, chapter_index,
            )
        )

    return results


# ---------------------------------------------------------------------------
# NEXT_SECTION edge generation
# ---------------------------------------------------------------------------


def extract_next_section_edges(chunks_df: pd.DataFrame) -> list[Relationship]:
    """Generate NEXT_SECTION edges from consecutive chunk_index within same document.

    Groups chunks by ``filename``, sorts by ``chunk_index``, and creates an
    edge between each consecutive pair.  Never crosses document boundaries.

    Args:
        chunks_df: DataFrame with ``id``, ``filename``, ``chunk_index`` columns.

    Returns:
        List of NEXT_SECTION Relationship objects.
    """
    edges: list[Relationship] = []

    for filename, group in chunks_df.groupby("filename"):
        sorted_group = group.sort_values("chunk_index")
        ids = sorted_group["id"].tolist()
        indices = sorted_group["chunk_index"].tolist()

        for i in range(len(ids) - 1):
            # Only create edge for consecutive chunk indices
            if indices[i + 1] == indices[i] + 1:
                edges.append(
                    Relationship(
                        source_id=ids[i],
                        target_id=ids[i + 1],
                        rel_type="NEXT_SECTION",
                        confidence=1.0,
                        raw_citation="",
                        source="chunk_index",
                    )
                )

    return edges


# ---------------------------------------------------------------------------
# Hierarchy extraction (Agency → Document → Chunk)
# ---------------------------------------------------------------------------


def extract_hierarchy(
    chunks_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[str, str]], list[tuple[str, str]]]:
    """Build Agency→Document→Chunk hierarchy from chunks_df.

    Uses the ``agency`` and ``filename`` fields as the authoritative source of
    document membership.  Each unique ``filename`` becomes one DocumentNode;
    each unique ``agency`` becomes one AgencyNode.  No citation prefix-matching
    or ``parent_section`` fallback is used — those approaches produce false edges
    because parent chapter citations rarely appear as standalone chunks.

    Args:
        chunks_df: DataFrame with ``id``, ``agency``, ``filename`` columns.

    Returns:
        agency_nodes: DataFrame with ``id``, ``label``, ``authority_level``
            (one row per unique agency).
        doc_nodes: DataFrame with ``id``, ``agency``, ``label``
            (one row per unique filename).
        agency_doc_edges: List of (agency_id, doc_id) tuples.
        doc_chunk_edges: List of (doc_id, chunk_id) tuples.
    """
    # Build AgencyNode DataFrame
    agencies = sorted(chunks_df["agency"].dropna().unique().tolist())
    agency_rows = [
        {
            "id": agency,
            "label": agency,
            "authority_level": AUTHORITY_LEVELS.get(agency, ""),
        }
        for agency in agencies
    ]
    agency_nodes = pd.DataFrame(agency_rows) if agency_rows else pd.DataFrame(
        columns=["id", "label", "authority_level"]
    )

    # Build DocumentNode DataFrame — one row per unique filename
    # Agency = agency of the first chunk encountered with that filename
    filename_to_agency: dict[str, str] = {}
    for _, row in chunks_df.iterrows():
        fn = str(row.get("filename", "") or "").strip()
        if fn and fn not in filename_to_agency:
            filename_to_agency[fn] = str(row.get("agency", "") or "").strip()

    doc_rows = [
        {
            "id": filename,
            "agency": agency,
            "label": Path(filename).stem,
        }
        for filename, agency in filename_to_agency.items()
    ]
    doc_nodes = pd.DataFrame(doc_rows) if doc_rows else pd.DataFrame(
        columns=["id", "agency", "label"]
    )

    # Build AGENCY_HAS_DOC edges
    agency_set = set(agency_nodes["id"].tolist()) if len(agency_nodes) > 0 else set()
    seen_ad: set[tuple[str, str]] = set()
    agency_doc_edges: list[tuple[str, str]] = []
    for _, row in doc_nodes.iterrows():
        ag = row["agency"]
        doc_id = row["id"]
        if ag in agency_set:
            key = (ag, doc_id)
            if key not in seen_ad:
                agency_doc_edges.append(key)
                seen_ad.add(key)

    # Build DOC_HAS_CHUNK edges
    doc_chunk_edges: list[tuple[str, str]] = []
    for _, row in chunks_df.iterrows():
        fn = str(row.get("filename", "") or "").strip()
        chunk_id = row["id"]
        if fn:
            doc_chunk_edges.append((fn, chunk_id))

    return agency_nodes, doc_nodes, agency_doc_edges, doc_chunk_edges


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_all_relationships(
    chunks_df: pd.DataFrame,
    citation_index: dict[str, str],
    chapter_index: dict[str, list[str]],
) -> tuple[list[Relationship], list[dict]]:
    """Extract all 6 rule-based relationship types from a DataFrame of chunks.

    Processing order per chunk:
    1. IMPLEMENTS (agency-specific)
    2. SUBJECT_TO
    3. DEFINED_BY
    4. AMENDED_BY
    5. CITES (deduplicated against 1-4)
    Then:
    6. NEXT_SECTION (from chunk_index ordering)

    Args:
        chunks_df: DataFrame with columns: id, text, agency, filename,
            chunk_index, citation, authority_level, section_number.
        citation_index: ``{normalized_citation -> chunk_id}`` from
            ``build_citation_index()``.
        chapter_index: ``{chapter_prefix -> [chunk_ids]}`` from
            ``build_citation_index()``.

    Returns:
        A 2-tuple of:
        - List of all resolved ``Relationship`` objects.
        - List of unresolved citation dicts (per D-06 schema).
    """
    all_relationships: list[Relationship] = []
    unresolved: list[dict] = []

    for _, row in chunks_df.iterrows():
        chunk_id = row["id"]
        text = row["text"]
        agency = row["agency"]
        already_extracted: set[str] = set()

        # 1. IMPLEMENTS
        implements = _extract_implements(
            text, chunk_id, agency, citation_index, chapter_index
        )
        for rel in implements:
            already_extracted.add(normalize_citation(rel.raw_citation))
        all_relationships.extend(
            r for r in implements if r.target_id != chunk_id
        )

        # 2. SUBJECT_TO
        subject_to = _extract_subject_to(
            text, chunk_id, citation_index, chapter_index
        )
        for rel in subject_to:
            already_extracted.add(normalize_citation(rel.raw_citation))
        all_relationships.extend(
            r for r in subject_to if r.target_id != chunk_id
        )

        # 3. DEFINED_BY
        defined_by = _extract_defined_by(
            text, chunk_id, citation_index, chapter_index
        )
        for rel in defined_by:
            already_extracted.add(normalize_citation(rel.raw_citation))
        all_relationships.extend(
            r for r in defined_by if r.target_id != chunk_id
        )

        # 4. AMENDED_BY
        amended_by = _extract_amended_by(
            text, chunk_id, citation_index, chapter_index
        )
        for rel in amended_by:
            already_extracted.add(normalize_citation(rel.raw_citation))
        all_relationships.extend(
            r for r in amended_by if r.target_id != chunk_id
        )

        # 5. CITES (deduplicated against 1-4)
        cites = _extract_cites(
            text, chunk_id, citation_index, chapter_index, already_extracted
        )
        all_relationships.extend(
            r for r in cites if r.target_id != chunk_id
        )

    # 6. NEXT_SECTION
    next_section = extract_next_section_edges(chunks_df)
    all_relationships.extend(next_section)

    # Deduplicate by (source_id, target_id, rel_type) triple
    seen_triples: set[tuple[str, str, str]] = set()
    deduped: list[Relationship] = []
    for rel in all_relationships:
        key = (rel.source_id, rel.target_id, rel.rel_type)
        if key not in seen_triples:
            seen_triples.add(key)
            deduped.append(rel)
    all_relationships = deduped

    # Collect unresolved citations
    for rel in all_relationships:
        if rel.target_id == "" and rel.rel_type != "NEXT_SECTION":
            unresolved.append(
                {
                    "source_chunk_id": rel.source_id,
                    "raw_citation": rel.raw_citation,
                    "relationship_type": rel.rel_type,
                    "reason": "no chunk found with matching citation",
                }
            )

    # Filter out unresolved from the resolved list (keep only resolved edges)
    resolved = [
        r for r in all_relationships
        if r.target_id != "" or r.rel_type == "NEXT_SECTION"
    ]

    return resolved, unresolved
