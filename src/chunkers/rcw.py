"""RCW (Revised Code of Washington) chunking strategy.

Splits RCW chapter documents on section headers (RCW XX.YY.ZZZ), detects and
separates index/cross-reference pages, extracts legislative history metadata,
and sub-chunks oversized sections at subsection boundaries with semchunk
as last resort.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.chunkers.base import (
    ChunkData,
    ChunkingStrategy,
    create_sub_chunker,
    extract_citations,
)

# Section header: RCW XX.YY.ZZZ followed by title text
# Handles standard (76.52.010), lettered titles (28B.10.016, 30B.04.002),
# and UCC hyphenated sections (62A.9A-101, 62A.9A-3061).
# Docling may render some section headers as Markdown headings (## RCW ...),
# so we allow an optional #{1,6} prefix before "RCW".
_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+)?(RCW\s+(\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4})\s+(.+))$",
    re.MULTILINE,
)

# Legislative history block in brackets at end of section
_LEGISLATIVE_HISTORY_RE = re.compile(
    r"\[(\d{4})\s+.*?\]", re.DOTALL
)

# Full legislative history block capture
_FULL_HISTORY_RE = re.compile(
    r"(\[\d{4}\s+.*?\])\s*$", re.DOTALL
)

# Top-level subsection markers for sub-chunking
_SUBSECTION_RE = re.compile(r"^\s*\(\d+\)", re.MULTILINE)

# Cross-reference index detection patterns
# Look for alphabetical topic listings with indented sub-topics
_INDEX_PATTERN_RE = re.compile(
    r"(?:^[A-Z][a-z]+(?:\s+\w+)*\s*$\n(?:\s+.+\n){2,}){3,}",
    re.MULTILINE,
)

# Simple heuristic: many lines matching "topic: RCW XX.YY.ZZZ" or similar
# Handles standard, lettered, and UCC section formats
_XREF_LINE_RE = re.compile(
    r"^\s+.*?(?:RCW\s+\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4}|\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4})",
    re.MULTILINE,
)

# Most recent year from legislative history
_HISTORY_YEAR_RE = re.compile(r"\[(\d{4})\s+")


class RCWChunker(ChunkingStrategy):
    """Chunker for Revised Code of Washington (RCW) documents.

    Handles three phases:
    1. Detect and separate cross-reference index pages
    2. Split body on RCW section headers
    3. Sub-chunk large sections at (1), (2) subsection level
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split RCW document text into section-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Phase 1: Detect and separate index/cross-reference pages
        first_section = _SECTION_RE.search(text)
        if first_section and first_section.start() > 500:
            preamble = text[: first_section.start()].strip()
            body = text[first_section.start() :]

            # Check if preamble looks like a cross-reference index
            xref_lines = _XREF_LINE_RE.findall(preamble)
            if len(xref_lines) >= 5:
                # Create cross-reference index chunk
                index_chunk = ChunkData(
                    text=preamble,
                    citation="",
                    section_title="Cross-Reference Index",
                    agency="RCW",
                    authority_level="state_statute",
                    content_type="cross_reference_index",
                    filename=filename,
                )
                # Sub-chunk if index is too large
                if self._count_tokens(preamble) <= self.max_tokens:
                    chunks.append(index_chunk)
                else:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    for j, piece in enumerate(sub_chunker(preamble)):
                        chunks.append(
                            ChunkData(
                                text=piece,
                                citation="",
                                section_title=f"Cross-Reference Index (part {j + 1})",
                                agency="RCW",
                                authority_level="state_statute",
                                content_type="cross_reference_index",
                                filename=filename,
                            )
                        )
        else:
            body = text

        # Phase 2: Split body on section headers
        section_matches = list(_SECTION_RE.finditer(body))

        if not section_matches:
            # No RCW section headers found — use fallback chunker to avoid
            # returning a single massive chunk
            if body.strip():
                chunks.extend(self._fallback_chunk(body.strip(), metadata, authority_level="state_statute"))
            return chunks

        for i, match in enumerate(section_matches):
            section_start = match.start()
            section_end = (
                section_matches[i + 1].start()
                if i + 1 < len(section_matches)
                else len(body)
            )

            section_text = body[section_start:section_end].strip()
            section_number = match.group(2)
            section_title = match.group(3).strip().rstrip(".")
            citation = f"RCW {section_number}"

            # Extract legislative history
            legislative_history = self._extract_legislative_history(
                section_text
            )
            last_amended_date = self._extract_last_amended_year(
                legislative_history
            )

            # Phase 3: Check token count and decide on sub-chunking
            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunk = self._make_chunk(
                    text=section_text,
                    citation=citation,
                    section_title=section_title,
                    section_number=section_number,
                    filename=filename,
                    legislative_history=legislative_history,
                    last_amended_date=last_amended_date,
                )
                chunks.append(chunk)
            else:
                # Try sub-chunking at (1), (2) subsection level first
                sub_chunks = self._split_at_subsections(
                    section_text,
                    citation,
                    section_title,
                    section_number,
                    filename,
                    legislative_history,
                    last_amended_date,
                )
                if sub_chunks:
                    chunks.extend(sub_chunks)
                else:
                    # Last resort: use semchunk
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    sub_texts = sub_chunker(section_text)
                    for j, sub_text in enumerate(sub_texts):
                        chunk = self._make_chunk(
                            text=sub_text,
                            citation=citation,
                            section_title=section_title,
                            section_number=section_number,
                            filename=filename,
                            legislative_history=legislative_history,
                            last_amended_date=last_amended_date,
                            subsection_id=f"{section_number}_part{j + 1}",
                        )
                        chunks.append(chunk)

        return chunks

    def _split_at_subsections(
        self,
        section_text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        legislative_history: Optional[str],
        last_amended_date: Optional[str],
    ) -> List[ChunkData] | None:
        """Try splitting a section at top-level (1), (2) subsection boundaries."""
        positions = [m.start() for m in _SUBSECTION_RE.finditer(section_text)]

        if len(positions) < 2:
            return None

        sub_texts: List[str] = []
        header_text = section_text[: positions[0]].strip()

        for k in range(len(positions)):
            end = (
                positions[k + 1]
                if k + 1 < len(positions)
                else len(section_text)
            )
            sub_text = section_text[positions[k] : end].strip()
            sub_texts.append(sub_text)

        chunks: List[ChunkData] = []
        if header_text and sub_texts:
            sub_texts[0] = header_text + "\n\n" + sub_texts[0]

        sub_chunker = None
        for k, sub_text in enumerate(sub_texts):
            if self._count_tokens(sub_text) > self.max_tokens:
                if sub_chunker is None:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(sub_text)):
                    chunk = self._make_chunk(
                        text=piece,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        filename=filename,
                        legislative_history=legislative_history,
                        last_amended_date=last_amended_date,
                        subsection_id=f"{section_number}({k + 1})_part{j + 1}",
                    )
                    chunks.append(chunk)
            else:
                chunk = self._make_chunk(
                    text=sub_text,
                    citation=citation,
                    section_title=section_title,
                    section_number=section_number,
                    filename=filename,
                    legislative_history=legislative_history,
                    last_amended_date=last_amended_date,
                    subsection_id=f"{section_number}({k + 1})",
                )
                chunks.append(chunk)

        return chunks if chunks else None

    def _make_chunk(
        self,
        text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        legislative_history: Optional[str] = None,
        last_amended_date: Optional[str] = None,
        subsection_id: Optional[str] = None,
    ) -> ChunkData:
        """Create a ChunkData for an RCW section/sub-section."""
        extra: Dict = {}
        if legislative_history:
            extra["legislative_history"] = legislative_history

        # parent_section: RCW chapter (XX.YY from XX.YY.ZZZ)
        if section_number:
            parts = section_number.rsplit(".", 1)
            parent = f"RCW {parts[0]}" if len(parts) > 1 else None
        else:
            parent = None

        return ChunkData(
            text=text,
            citation=citation,
            section_title=section_title,
            section_number=section_number,
            subsection_id=subsection_id,
            agency="RCW",
            authority_level="state_statute",
            content_type="substantive",
            last_amended_date=last_amended_date,
            filename=filename,
            parent_section=parent,
            metadata=extra,
        )

    @staticmethod
    def _extract_legislative_history(section_text: str) -> Optional[str]:
        """Extract the full legislative history block from section text."""
        match = _FULL_HISTORY_RE.search(section_text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_last_amended_year(
        legislative_history: Optional[str],
    ) -> Optional[str]:
        """Extract the most recent year from legislative history."""
        if not legislative_history:
            return None
        match = _HISTORY_YEAR_RE.search(legislative_history)
        if match:
            return match.group(1)
        return None
