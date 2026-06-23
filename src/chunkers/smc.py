"""SMC (Seattle Municipal Code) chunking strategy.

Splits SMC documents on section headers (XX.YY.ZZZ - Title), handles
ordinance history blocks, table detection, definition sections, and strips
web-to-PDF footers. Sub-chunks at A./B. subsection level with semchunk
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

# Section header: XX.YY.ZZZ - Title (handles -, en-dash, em-dash)
# Docling may render some section headers as Markdown headings (## XX.YY.ZZZ ...),
# so we allow an optional #{1,6} prefix.
_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+)?((\d{1,2}\.\d{2,3}\.\d{3})\s*[-\u2013\u2014]\s*(.+))$",
    re.MULTILINE,
)

# Ordinance history at end of section
_ORDINANCE_HISTORY_RE = re.compile(
    r"\(Ord\.\s+\d+.*?\)", re.DOTALL
)

# Web-to-PDF footer/timestamp patterns to strip
_WEB_FOOTER_RE = re.compile(
    r"The Seattle Municipal Code.*?$|^\d{1,2}/\d{1,2}/\d{4}.*?$",
    re.MULTILINE,
)

# Uppercase-letter subsection markers for sub-chunking (A., B., C.)
_LETTER_SUBSECTION_RE = re.compile(r"^\s*[A-Z]\.\s+", re.MULTILINE)

# Definition entry pattern: "Term" means ...
_DEFINITION_RE = re.compile(
    r'"[^"]+"\s+means\b', re.MULTILINE
)

# Table detection (Markdown table rows start with |)
_TABLE_RE = re.compile(r"(?:Table\s+[A-Z\d]|^\|)", re.MULTILINE)

# Table type classification keywords
_TABLE_TYPE_KEYWORDS = {
    "fee": "fee_schedule",
    "dimension": "dimensional",
    "zone": "zoning",
    "height": "dimensional",
    "setback": "dimensional",
    "parking": "dimensional",
}

# Year from ordinance history
_ORD_YEAR_RE = re.compile(r"(\d{4})\s*[;)]")


class SMCChunker(ChunkingStrategy):
    """Chunker for Seattle Municipal Code (SMC) documents.

    Handles section splitting, ordinance history, table detection,
    definition sections, and web-to-PDF footer stripping.
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split SMC document text into section-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Strip web-to-PDF footers and timestamps
        text = _WEB_FOOTER_RE.sub("", text)

        # Find all section headers
        section_matches = list(_SECTION_RE.finditer(text))

        if not section_matches:
            # No SMC section headers found — use fallback chunker to avoid
            # returning a single massive chunk
            if text.strip():
                chunks.extend(self._fallback_chunk(text.strip(), metadata, authority_level="local_statute"))
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
            citation = f"SMC {section_number}"
            chapter = ".".join(section_number.split(".")[:2])

            # Extract ordinance history
            ordinance_history = self._extract_ordinance_history(section_text)
            last_amended_date = self._extract_last_amended_year(
                ordinance_history
            )

            # Detect content type
            is_definition = bool(_DEFINITION_RE.search(section_text))
            has_table = bool(_TABLE_RE.search(section_text))
            content_type = "definition" if is_definition else "substantive"

            # Determine table type if table present
            table_type = None
            if has_table:
                table_type = self._classify_table(section_text)

            # Check token count
            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunk = self._make_chunk(
                    text=section_text,
                    citation=citation,
                    section_title=section_title,
                    section_number=section_number,
                    filename=filename,
                    chapter=chapter,
                    ordinance_history=ordinance_history,
                    last_amended_date=last_amended_date,
                    content_type=content_type,
                    is_table=has_table,
                    table_type=table_type,
                )
                chunks.append(chunk)
            else:
                # Try sub-chunking at A., B. subsection level
                sub_chunks = self._split_at_letter_subsections(
                    section_text,
                    citation,
                    section_title,
                    section_number,
                    filename,
                    chapter,
                    ordinance_history,
                    last_amended_date,
                    content_type,
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
                            chapter=chapter,
                            ordinance_history=ordinance_history,
                            last_amended_date=last_amended_date,
                            content_type=content_type,
                            is_table=bool(_TABLE_RE.search(sub_text)),
                            table_type=self._classify_table(sub_text)
                            if _TABLE_RE.search(sub_text)
                            else None,
                            subsection_id=f"{section_number}_part{j + 1}",
                        )
                        chunks.append(chunk)

        return chunks

    def _split_at_letter_subsections(
        self,
        section_text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        chapter: str,
        ordinance_history: Optional[str],
        last_amended_date: Optional[str],
        content_type: str,
    ) -> List[ChunkData] | None:
        """Try splitting a section at A., B. subsection boundaries."""
        positions = [
            m.start() for m in _LETTER_SUBSECTION_RE.finditer(section_text)
        ]

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
            has_table = bool(_TABLE_RE.search(sub_text))
            if self._count_tokens(sub_text) > self.max_tokens:
                if sub_chunker is None:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(sub_text)):
                    chunks.append(
                        self._make_chunk(
                            text=piece,
                            citation=citation,
                            section_title=section_title,
                            section_number=section_number,
                            filename=filename,
                            chapter=chapter,
                            ordinance_history=ordinance_history,
                            last_amended_date=last_amended_date,
                            content_type=content_type,
                            is_table=bool(_TABLE_RE.search(piece)),
                            table_type=self._classify_table(piece)
                            if _TABLE_RE.search(piece)
                            else None,
                            subsection_id=f"{section_number}({chr(65 + k)})_part{j + 1}",
                        )
                    )
            else:
                chunks.append(
                    self._make_chunk(
                        text=sub_text,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        filename=filename,
                        chapter=chapter,
                        ordinance_history=ordinance_history,
                        last_amended_date=last_amended_date,
                        content_type=content_type,
                        is_table=has_table,
                        table_type=self._classify_table(sub_text)
                        if has_table
                        else None,
                        subsection_id=f"{section_number}({chr(65 + k)})",
                    )
                )

        return chunks if chunks else None

    def _make_chunk(
        self,
        text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        chapter: str = "",
        ordinance_history: Optional[str] = None,
        last_amended_date: Optional[str] = None,
        content_type: str = "substantive",
        is_table: bool = False,
        table_type: Optional[str] = None,
        subsection_id: Optional[str] = None,
    ) -> ChunkData:
        """Create a ChunkData for an SMC section/sub-section."""
        extra: Dict = {}
        if chapter:
            extra["chapter"] = chapter
        if ordinance_history:
            extra["ordinance_history"] = ordinance_history

        return ChunkData(
            text=text,
            citation=citation,
            section_title=section_title,
            section_number=section_number,
            subsection_id=subsection_id,
            agency="SMC",
            authority_level="local_statute",
            content_type=content_type,
            last_amended_date=last_amended_date,
            is_table=is_table,
            table_type=table_type,
            filename=filename,
            parent_section=f"SMC {chapter}" if chapter else None,
            metadata=extra,
        )

    @staticmethod
    def _extract_ordinance_history(section_text: str) -> Optional[str]:
        """Extract the ordinance history block from section text."""
        # Find the last (Ord. ...) block in the section
        matches = list(_ORDINANCE_HISTORY_RE.finditer(section_text))
        if matches:
            return matches[-1].group(0)
        return None

    @staticmethod
    def _extract_last_amended_year(
        ordinance_history: Optional[str],
    ) -> Optional[str]:
        """Extract the most recent year from ordinance history."""
        if not ordinance_history:
            return None
        years = _ORD_YEAR_RE.findall(ordinance_history)
        if years:
            return max(years)
        return None

    @staticmethod
    def _classify_table(text: str) -> str:
        """Classify table type based on content keywords."""
        text_lower = text.lower()
        for keyword, ttype in _TABLE_TYPE_KEYWORDS.items():
            if keyword in text_lower:
                return ttype
        return "other"
