"""SPU (Seattle Public Utilities) Design Standards chunking strategy.

Splits SPU documents at decimal subsection headers (X.Y or X.Y.Z), handles
extensive table content with type classification, tags mandatory language
(must/shall), and creates standalone chunks for definitions tables.
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

# Section/subsection header: ## X.Y[.Z[.W]] followed by title
# Docling typically renders SPU section headings with markdown ## prefix
# (e.g., "## 10.1 KEY TERMS"), but we tolerate plain text too for robustness.
# Supports up to 4-level numbering (e.g., 4.3.1.1)
_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+)?((\d{1,2}(?:\.\d{1,2}){1,3})\s+(.+))$", re.MULTILINE
)

# Table detection: Markdown tables start with | or "Table N" labels
_TABLE_RE = re.compile(r"(?:Table\s+\d|^\|)", re.MULTILINE)

# Markdown table row pattern (for detecting table-heavy chunks)
_TABLE_ROW_RE = re.compile(r"^\|.+\|$", re.MULTILINE)

# Mandatory language detection
_MANDATORY_RE = re.compile(r"\b(?:must|shall)\b", re.IGNORECASE)

# Table type classification keywords
_TABLE_TYPE_KEYWORDS = [
    (re.compile(r"\b(?:abbreviation|acronym)\b", re.IGNORECASE), "abbreviation"),
    (re.compile(r"\b(?:definition|means|defined\s+as)\b", re.IGNORECASE), "definition"),
    (re.compile(r"\b(?:diameter|dimension|size|width)\b", re.IGNORECASE), "dimensional"),
    (re.compile(r"\b(?:material|specification)\b", re.IGNORECASE), "specification"),
]


class SPUChunker(ChunkingStrategy):
    """Chunker for Seattle Public Utilities Design Standards documents.

    Handles decimal hierarchy splitting, table extraction with type
    classification, mandatory language tagging, and standalone definition
    table chunks.
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split SPU document into subsection-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Find all section/subsection headers
        section_matches = list(_SECTION_RE.finditer(text))

        if not section_matches:
            # No SPU section headers found — use fallback chunker to avoid
            # returning a single massive chunk
            if text.strip():
                chunks.extend(self._fallback_chunk(text.strip(), metadata, authority_level="guidance"))
            return chunks

        # Handle any text before first section header
        preamble = text[: section_matches[0].start()].strip()
        if preamble and len(preamble) > 50:
            preamble_tokens = self._count_tokens(preamble)
            if preamble_tokens <= self.max_tokens:
                chunks.append(
                    self._make_chunk(
                        text=preamble,
                        citation="",
                        section_title="Introduction",
                        section_number="",
                        filename=filename,
                    )
                )

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
            citation = f"SPU {section_number}"

            # Detect table content
            has_table = bool(_TABLE_RE.search(section_text))
            table_type = self._classify_table(section_text) if has_table else None

            # Detect mandatory language
            has_mandatory = bool(_MANDATORY_RE.search(section_text))

            # Detect if this is a definitions section
            is_definition = (
                table_type == "definition"
                or "definition" in section_title.lower()
            )

            # Determine content type
            if is_definition:
                content_type = "definition"
            elif table_type == "specification":
                content_type = "specification"
            else:
                content_type = "substantive"

            # Check token count
            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunks.append(
                    self._make_chunk(
                        text=section_text,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        filename=filename,
                        is_table=has_table,
                        table_type=table_type,
                        mandatory=has_mandatory,
                        content_type=content_type,
                    )
                )
            else:
                # Try to separate table content from prose
                table_chunks, prose_text = self._separate_tables(
                    section_text,
                    citation,
                    section_title,
                    section_number,
                    filename,
                )
                if table_chunks:
                    chunks.extend(table_chunks)

                # Sub-chunk remaining prose if still too large
                if prose_text:
                    prose_tokens = self._count_tokens(prose_text)
                    if prose_tokens <= self.max_tokens:
                        chunks.append(
                            self._make_chunk(
                                text=prose_text,
                                citation=citation,
                                section_title=section_title,
                                section_number=section_number,
                                filename=filename,
                                mandatory=bool(
                                    _MANDATORY_RE.search(prose_text)
                                ),
                                content_type=content_type,
                            )
                        )
                    else:
                        sub_chunker = create_sub_chunker(self.max_tokens)
                        for j, piece in enumerate(sub_chunker(prose_text)):
                            chunks.append(
                                self._make_chunk(
                                    text=piece,
                                    citation=citation,
                                    section_title=section_title,
                                    section_number=section_number,
                                    filename=filename,
                                    mandatory=bool(
                                        _MANDATORY_RE.search(piece)
                                    ),
                                    content_type=content_type,
                                    subsection_id=f"{section_number}_part{j + 1}",
                                )
                            )

                # If no table separation happened, just sub-chunk the whole thing
                if not table_chunks and not prose_text:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    for j, piece in enumerate(sub_chunker(section_text)):
                        chunks.append(
                            self._make_chunk(
                                text=piece,
                                citation=citation,
                                section_title=section_title,
                                section_number=section_number,
                                filename=filename,
                                is_table=bool(_TABLE_RE.search(piece)),
                                table_type=self._classify_table(piece)
                                if _TABLE_RE.search(piece)
                                else None,
                                mandatory=bool(_MANDATORY_RE.search(piece)),
                                content_type=content_type,
                                subsection_id=f"{section_number}_part{j + 1}",
                            )
                        )

        return chunks

    def _separate_tables(
        self,
        section_text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
    ) -> tuple[List[ChunkData], str]:
        """Separate table content from prose in an oversized section.

        Returns a tuple of (table_chunks, remaining_prose_text).
        """
        lines = section_text.split("\n")
        table_blocks: List[List[str]] = []
        prose_lines: List[str] = []
        current_table: List[str] = []
        in_table = False

        for line in lines:
            if line.strip().startswith("|"):
                in_table = True
                current_table.append(line)
            else:
                if in_table:
                    # End of table block
                    table_blocks.append(current_table)
                    current_table = []
                    in_table = False
                prose_lines.append(line)

        if current_table:
            table_blocks.append(current_table)

        table_chunks: List[ChunkData] = []
        for idx, block in enumerate(table_blocks):
            table_text = "\n".join(block)
            if not table_text.strip():
                continue
            table_type = self._classify_table(table_text)
            is_definition = table_type == "definition"

            table_tokens = self._count_tokens(table_text)
            if table_tokens <= self.max_tokens:
                table_chunks.append(
                    self._make_chunk(
                        text=table_text,
                        citation=citation,
                        section_title=f"{section_title} (Table {idx + 1})",
                        section_number=section_number,
                        filename=filename,
                        is_table=True,
                        table_type=table_type,
                        content_type="definition" if is_definition else "substantive",
                        subsection_id=f"{section_number}_table{idx + 1}",
                    )
                )
            else:
                # Table too large; sub-chunk it
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(table_text)):
                    table_chunks.append(
                        self._make_chunk(
                            text=piece,
                            citation=citation,
                            section_title=f"{section_title} (Table {idx + 1}, part {j + 1})",
                            section_number=section_number,
                            filename=filename,
                            is_table=True,
                            table_type=table_type,
                            content_type="definition" if is_definition else "substantive",
                            subsection_id=f"{section_number}_table{idx + 1}_part{j + 1}",
                        )
                    )

        remaining_prose = "\n".join(prose_lines).strip()
        return table_chunks, remaining_prose

    def _make_chunk(
        self,
        text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        is_table: bool = False,
        table_type: Optional[str] = None,
        mandatory: bool = False,
        content_type: str = "substantive",
        subsection_id: Optional[str] = None,
    ) -> ChunkData:
        """Create a ChunkData for an SPU section/sub-section."""
        extra: Dict = {}
        if mandatory:
            extra["mandatory"] = True

        # parent_section: parent decimal (3.2.1 → 3.2, 3.2 → 3)
        if section_number:
            parts = section_number.rsplit(".", 1)
            parent = parts[0] if len(parts) > 1 else None
        else:
            parent = None

        return ChunkData(
            text=text,
            citation=citation,
            section_title=section_title,
            section_number=section_number,
            subsection_id=subsection_id,
            agency="SPU",
            authority_level="guidance",
            content_type=content_type,
            is_table=is_table,
            table_type=table_type,
            filename=filename,
            parent_section=parent,
            metadata=extra,
        )

    @staticmethod
    def _classify_table(text: str) -> str:
        """Classify table type based on content keywords."""
        for pattern, ttype in _TABLE_TYPE_KEYWORDS:
            if pattern.search(text):
                return ttype
        return "other"
