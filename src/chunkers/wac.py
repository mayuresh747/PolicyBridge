"""WAC (Washington Administrative Code) chunking strategy.

Splits WAC chapter documents on section headers (WAC XXX-YYY-ZZZ), extracts
statutory authority metadata, and sub-chunks oversized sections at subsection
boundaries (1), (2) with semchunk as last resort.
"""

from __future__ import annotations

import re
from typing import Dict, List

from src.chunkers.base import (
    ChunkData,
    ChunkingStrategy,
    create_sub_chunker,
    extract_citations,
)

# Section header: WAC XXX-YYY-ZZZ followed by title text
# Docling may render some section headers as Markdown headings (## WAC ...),
# so we allow an optional #{1,6} prefix before "WAC".
_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+)?(WAC\s+(\d{3}-\d{2,3}-\d{3})\s+(.+))$", re.MULTILINE
)

# Statutory Authority block at end of each section
_STATUTORY_AUTHORITY_RE = re.compile(
    r"^\[Statutory Authority:.*?(?:\]|$)", re.MULTILINE | re.DOTALL
)

# Top-level subsection markers for sub-chunking
_SUBSECTION_RE = re.compile(r"^\s*\(\d+\)", re.MULTILINE)

# Part groupings within a chapter
_PART_RE = re.compile(r"^(Part\s+\w+[:\s]+.+)$", re.MULTILINE)

# Effective date from WSR filing info in Statutory Authority block
_EFFECTIVE_DATE_RE = re.compile(
    r"effective\s+(\d{1,2}/\d{1,2}/\d{2,4})", re.IGNORECASE
)

# RCW citations within Statutory Authority block
_STAT_AUTH_RCW_RE = re.compile(
    r"RCW\s+([\d.]+(?:\s*(?:,\s*and\s+|and\s+|,\s*)[\d.]+)*)"
)


class WACChunker(ChunkingStrategy):
    """Chunker for Washington Administrative Code (WAC) documents.

    Splits on WAC section headers, preserves Statutory Authority blocks,
    and sub-chunks at (1), (2) subsection boundaries when sections exceed
    max_tokens (2000).
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split WAC document text into section-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects, one per section (or sub-section).
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Detect Part groupings for metadata
        current_part = None
        part_positions: List[tuple[int, str]] = []
        for m in _PART_RE.finditer(text):
            part_positions.append((m.start(), m.group(1).strip()))

        # Find all section header positions
        section_matches = list(_SECTION_RE.finditer(text))

        if not section_matches:
            # No WAC section headers found — use fallback chunker to avoid
            # returning a single massive chunk
            if text.strip():
                chunks.extend(self._fallback_chunk(text.strip(), metadata, authority_level="state_admin_rule"))
            return chunks

        for i, match in enumerate(section_matches):
            section_start = match.start()
            section_end = (
                section_matches[i + 1].start()
                if i + 1 < len(section_matches)
                else len(text)
            )

            section_text = text[section_start:section_end].strip()
            section_number = match.group(2)
            section_title = match.group(3).strip().rstrip(".")
            citation = f"WAC {section_number}"

            # Determine current Part group
            current_part = self._get_current_part(
                section_start, part_positions
            )

            # Check token count and decide on sub-chunking
            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunk = self._make_chunk(
                    text=section_text,
                    citation=citation,
                    section_title=section_title,
                    section_number=section_number,
                    filename=filename,
                    part_group=current_part,
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
                    current_part,
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
                            part_group=current_part,
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
        part_group: str | None,
    ) -> List[ChunkData] | None:
        """Try splitting a section at top-level (1), (2) subsection boundaries.

        Returns None if subsection splitting doesn't produce valid chunks
        (e.g., no subsection markers found or all sub-chunks still too large).
        """
        positions = [m.start() for m in _SUBSECTION_RE.finditer(section_text)]

        if len(positions) < 2:
            return None

        # Build sub-section texts
        sub_texts: List[str] = []
        # Include header text before first subsection
        header_text = section_text[: positions[0]].strip()

        for k in range(len(positions)):
            end = positions[k + 1] if k + 1 < len(positions) else len(section_text)
            sub_text = section_text[positions[k] : end].strip()
            sub_texts.append(sub_text)

        chunks: List[ChunkData] = []
        # Prepend header to first sub-text
        if header_text and sub_texts:
            sub_texts[0] = header_text + "\n\n" + sub_texts[0]

        sub_chunker = None
        for k, sub_text in enumerate(sub_texts):
            if self._count_tokens(sub_text) > self.max_tokens:
                # Use semchunk as last resort for oversized subsections
                if sub_chunker is None:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(sub_text)):
                    chunk = self._make_chunk(
                        text=piece,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        filename=filename,
                        part_group=part_group,
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
                    part_group=part_group,
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
        part_group: str | None,
        subsection_id: str | None = None,
    ) -> ChunkData:
        """Create a ChunkData for a WAC section/sub-section."""
        # Extract statutory authority info from this chunk's text
        statutory_authority = ""
        effective_date = None
        stat_match = _STATUTORY_AUTHORITY_RE.search(text)
        if stat_match:
            stat_block = stat_match.group(0)
            # Extract RCW citations from statutory authority block
            rcw_match = _STAT_AUTH_RCW_RE.search(stat_block)
            if rcw_match:
                statutory_authority = rcw_match.group(0)
            # Extract effective date
            date_match = _EFFECTIVE_DATE_RE.search(stat_block)
            if date_match:
                effective_date = date_match.group(1)

        extra: Dict = {}
        if statutory_authority:
            extra["statutory_authority"] = statutory_authority
        if part_group:
            extra["part_group"] = part_group

        # parent_section: use Part group if available, else WAC chapter (XXX-YYY)
        if part_group:
            parent = part_group
        elif section_number:
            parts = section_number.split("-")
            parent = f"WAC {'-'.join(parts[:2])}" if len(parts) >= 2 else None
        else:
            parent = None

        return ChunkData(
            text=text,
            citation=citation,
            section_title=section_title,
            section_number=section_number,
            subsection_id=subsection_id,
            agency="WAC",
            authority_level="state_admin_rule",
            content_type="substantive",
            effective_date=effective_date,
            filename=filename,
            parent_section=parent,
            metadata=extra,
        )

    @staticmethod
    def _get_current_part(
        position: int, part_positions: List[tuple[int, str]]
    ) -> str | None:
        """Determine the current Part group for a given text position."""
        current = None
        for pos, name in part_positions:
            if pos <= position:
                current = name
            else:
                break
        return current
