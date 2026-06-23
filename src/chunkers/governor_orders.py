"""Governor Executive Orders chunking strategy.

Splits executive orders at the WHEREAS/NOW THEREFORE boundary for longer
orders, keeps short orders as single chunks, strips identical savings
clause boilerplate, and extracts header metadata (EO number, title,
governor name, effective date).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.chunkers.base import (
    MIN_CHUNK_TOKENS,
    ChunkData,
    ChunkingStrategy,
    create_sub_chunker,
    extract_citations,
)

# Executive Order number
_EO_NUMBER_RE = re.compile(
    r"EXECUTIVE ORDER\s+(\d{2}-\d{2})", re.IGNORECASE
)

# Title: ALL-CAPS line after EO number
_EO_TITLE_RE = re.compile(
    r"EXECUTIVE ORDER\s+\d{2}-\d{2}\s*\n+\s*([A-Z][A-Z\s,;:\-]+)$",
    re.MULTILINE,
)

# WHEREAS / NOW THEREFORE boundary
_NOW_THEREFORE_RE = re.compile(
    r"NOW,?\s+THEREFORE", re.MULTILINE | re.IGNORECASE
)

# Governor name from NOW THEREFORE clause
_GOVERNOR_RE = re.compile(
    r"NOW,?\s+THEREFORE,?\s+I,?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    re.IGNORECASE,
)

# Boilerplate savings clause to strip
_BOILERPLATE_RE = re.compile(
    r"This (?:Order|order) (?:is not|shall not be) intended to confer.*?(?=\n\n|\Z)",
    re.DOTALL,
)

# Effective date from "take effect" or "Signed" clause
_EFFECTIVE_DATE_RE = re.compile(
    r"(?:take effect|signed|Signed).*?(\w+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)

# Expiration/sunset date
_EXPIRATION_RE = re.compile(
    r"(?:expire|sunset|terminate).*?(\w+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)

# Implementing agency detection
_AGENCY_RE = re.compile(
    r"(?:Department of|Office of|Commission on|Board of)\s+([A-Z][A-Za-z\s]+?)(?:\s*[,;.]|\s+(?:shall|is|to|and)\b)",
)

# WHEREAS detection for splitting
_WHEREAS_RE = re.compile(r"^\s*WHEREAS\b", re.MULTILINE)

# Token threshold for whole-doc vs split
_WHOLE_DOC_THRESHOLD = 1500


class GovernorOrderChunker(ChunkingStrategy):
    """Chunker for Washington Governor Executive Orders.

    Most orders are 2-3 pages and are kept as single chunks. Longer orders
    are split at the WHEREAS/NOW THEREFORE boundary. Savings clause
    boilerplate is stripped from all orders.
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split executive order document into chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Phase 1: Extract header metadata
        eo_number = self._extract_eo_number(text)
        eo_title = self._extract_title(text)
        # Fallback: derive title from filename when regex doesn't match
        if not eo_title and filename:
            eo_title = filename.replace(".pdf", "").replace("_", " ").strip()
        governor = self._extract_governor(text)
        effective_date = self._extract_effective_date(text)
        expiration_date = self._extract_expiration_date(text)
        implementing_agency = self._extract_implementing_agency(text)

        citation = f"EO {eo_number}" if eo_number else ""

        extra: Dict = {}
        if governor:
            extra["governor"] = governor
        if expiration_date:
            extra["expiration_date"] = expiration_date
        if implementing_agency:
            extra["implementing_agency"] = implementing_agency

        # Phase 2: Strip boilerplate savings clause
        text = _BOILERPLATE_RE.sub("", text).strip()

        # Extract cross-agency citations
        cites = extract_citations(text)
        if cites:
            extra["cross_citations"] = cites

        # Phase 3: Determine size and chunking approach
        token_count = self._count_tokens(text)

        if token_count <= _WHOLE_DOC_THRESHOLD:
            # Single chunk for short orders (most orders)
            chunks.append(
                ChunkData(
                    text=text,
                    citation=citation,
                    section_title=eo_title,
                    agency="Governor Orders",
                    authority_level="state_executive_order",
                    content_type="substantive",
                    effective_date=effective_date,
                    filename=filename,
                    parent_section=citation,
                    metadata=extra,
                )
            )
        else:
            # Split at WHEREAS / NOW THEREFORE boundary
            now_match = _NOW_THEREFORE_RE.search(text)
            if now_match:
                whereas_text = text[: now_match.start()].strip()
                therefore_text = text[now_match.start() :].strip()

                # WHEREAS recitals chunk
                if whereas_text:
                    whereas_tokens = self._count_tokens(whereas_text)
                    if whereas_tokens <= self.max_tokens:
                        chunks.append(
                            ChunkData(
                                text=whereas_text,
                                citation=citation,
                                section_title=f"{eo_title} - WHEREAS Recitals"
                                if eo_title
                                else "WHEREAS Recitals",
                                agency="Governor Orders",
                                authority_level="state_executive_order",
                                content_type="substantive",
                                effective_date=effective_date,
                                filename=filename,
                                parent_section=citation,
                                metadata=extra,
                            )
                        )
                    else:
                        sub_chunker = create_sub_chunker(self.max_tokens)
                        for j, piece in enumerate(sub_chunker(whereas_text)):
                            chunks.append(
                                ChunkData(
                                    text=piece,
                                    citation=citation,
                                    section_title=f"{eo_title} - WHEREAS (part {j + 1})"
                                    if eo_title
                                    else f"WHEREAS (part {j + 1})",
                                    agency="Governor Orders",
                                    authority_level="state_executive_order",
                                    content_type="substantive",
                                    effective_date=effective_date,
                                    filename=filename,
                                    parent_section=citation,
                                    metadata=extra,
                                )
                            )

                # NOW THEREFORE directives chunk
                if therefore_text:
                    therefore_tokens = self._count_tokens(therefore_text)
                    if therefore_tokens <= self.max_tokens:
                        chunks.append(
                            ChunkData(
                                text=therefore_text,
                                citation=citation,
                                section_title=f"{eo_title} - Directives"
                                if eo_title
                                else "Directives",
                                agency="Governor Orders",
                                authority_level="state_executive_order",
                                content_type="substantive",
                                effective_date=effective_date,
                                filename=filename,
                                parent_section=citation,
                                metadata=extra,
                            )
                        )
                    else:
                        sub_chunker = create_sub_chunker(self.max_tokens)
                        for j, piece in enumerate(sub_chunker(therefore_text)):
                            chunks.append(
                                ChunkData(
                                    text=piece,
                                    citation=citation,
                                    section_title=f"{eo_title} - Directives (part {j + 1})"
                                    if eo_title
                                    else f"Directives (part {j + 1})",
                                    agency="Governor Orders",
                                    authority_level="state_executive_order",
                                    content_type="substantive",
                                    effective_date=effective_date,
                                    filename=filename,
                                    parent_section=citation,
                                    metadata=extra,
                                )
                            )
            else:
                # No NOW THEREFORE found; use semchunk on full text
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(text)):
                    chunks.append(
                        ChunkData(
                            text=piece,
                            citation=citation,
                            section_title=f"{eo_title} (part {j + 1})"
                            if eo_title
                            else f"Part {j + 1}",
                            agency="Governor Orders",
                            authority_level="state_executive_order",
                            content_type="substantive",
                            effective_date=effective_date,
                            filename=filename,
                            parent_section=citation,
                            metadata=extra,
                        )
                    )

        # Filter out garbage chunks below minimum token threshold
        chunks = [c for c in chunks if self._count_tokens(c.text) >= MIN_CHUNK_TOKENS]
        return chunks

    @staticmethod
    def _extract_eo_number(text: str) -> Optional[str]:
        """Extract Executive Order number from text."""
        match = _EO_NUMBER_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract the title from the ALL-CAPS line after EO number."""
        match = _EO_TITLE_RE.search(text)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_governor(text: str) -> Optional[str]:
        """Extract governor name from NOW THEREFORE clause."""
        match = _GOVERNOR_RE.search(text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_effective_date(text: str) -> Optional[str]:
        """Extract effective date from 'take effect' or 'Signed' clause."""
        match = _EFFECTIVE_DATE_RE.search(text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_expiration_date(text: str) -> Optional[str]:
        """Extract expiration/sunset date if present."""
        match = _EXPIRATION_RE.search(text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_implementing_agency(text: str) -> Optional[str]:
        """Extract implementing agency from directive text."""
        match = _AGENCY_RE.search(text)
        return match.group(0).strip().rstrip(",.;") if match else None
