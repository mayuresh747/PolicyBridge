"""Seattle Director's Rules (DIR) chunking strategy.

Splits Director's Rules documents by extracting the structured metadata
header block and then either keeping the body as a single chunk (for short
rules <1500 tokens) or splitting at decimal section headers (1.0, 2.0, 3.0).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from src.chunkers.base import (
    ChunkData,
    ChunkingStrategy,
    create_sub_chunker,
    extract_citations,
)

# Body starts at section 1.0
# Docling may render section headers as Markdown headings (## 1.0 Purpose),
# so we allow an optional #{1,6} prefix.
_BODY_START_RE = re.compile(r"^(?:#{1,6}\s+)?1\.0\s+", re.MULTILINE)

# Decimal section headers (1.0, 2.0, 3.0, etc.)
# Docling may render section headers as Markdown headings (## 2.0 Definitions),
# so we allow an optional #{1,6} prefix.
_SECTION_RE = re.compile(r"^(?:#{1,6}\s+)?(\d+\.\d*)\s+(.+)$", re.MULTILINE)

# DR citation pattern
_DR_CITATION_RE = re.compile(
    r"(?:DR|Director.?s?\s+Rule)\s+(\d{1,2}-\d{4})", re.IGNORECASE
)

# Filename citation pattern: extract XX-YYYY from filenames like "31-2017 - Streets Illustrated.pdf"
_FILENAME_CITATION_RE = re.compile(r"^(\d{1,2}-\d{4})")

# Header field extraction patterns
_HEADER_FIELDS = {
    "supersedes": re.compile(r"Supersedes:\s*(.+?)(?:\n|$)", re.IGNORECASE),
    "publication_date": re.compile(
        r"Publication:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
    "effective_date": re.compile(
        r"Effective:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
    "subject": re.compile(r"Subject:\s*(.+?)(?:\n|$)", re.IGNORECASE),
    "code_reference": re.compile(
        r"Code/Section Reference:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
    "rule_type": re.compile(
        r"Type of Rule:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
    "ordinance_authority": re.compile(
        r"Ordinance Authority:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
    "department": re.compile(
        r"Applicant:\s*(.+?)(?:\n|$)", re.IGNORECASE
    ),
}

# Token threshold for whole-doc vs section split
_WHOLE_DOC_THRESHOLD = 1500


class DirectorRuleChunker(ChunkingStrategy):
    """Chunker for Seattle Director's Rules documents.

    Short rules (<1500 tokens) are kept as single chunks. Longer rules
    are split at decimal section headers (1.0, 2.0, 3.0). A standalone
    metadata chunk is always created from the header block.
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split Director's Rule document into chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Phase 1: Extract structured metadata header
        header_fields = self._extract_header_fields(text)

        # Extract DR citation from document text (with filename fallback)
        citation = self._extract_citation(text, filename)
        section_title = header_fields.get("subject", "")
        effective_date = header_fields.get("effective_date")

        # Separate header and body
        body_match = _BODY_START_RE.search(text)
        if body_match:
            header_text = text[: body_match.start()].strip()
            body_text = text[body_match.start() :].strip()
        else:
            # No clear 1.0 marker; treat entire text as body
            header_text = ""
            body_text = text.strip()

        # Create standalone metadata chunk from header
        if header_text:
            meta_chunk = ChunkData(
                text=header_text,
                citation=citation,
                section_title=section_title,
                agency="Seattle DIR",
                authority_level="local_admin_rule",
                content_type="header_metadata",
                effective_date=effective_date,
                filename=filename,
                parent_section=citation,
                metadata=self._build_metadata(header_fields),
            )
            chunks.append(meta_chunk)

        # Phase 2: Determine chunking approach for body
        body_tokens = self._count_tokens(body_text)

        if body_tokens <= _WHOLE_DOC_THRESHOLD:
            # Single chunk for short rules
            if body_text:
                chunk = ChunkData(
                    text=body_text,
                    citation=citation,
                    section_title=section_title,
                    agency="Seattle DIR",
                    authority_level="local_admin_rule",
                    content_type="substantive",
                    effective_date=effective_date,
                    filename=filename,
                    parent_section=citation,
                    metadata=self._build_metadata(header_fields),
                )
                chunks.append(chunk)
        else:
            # Split at decimal section headers
            section_chunks = self._split_at_sections(
                body_text,
                citation,
                section_title,
                filename,
                effective_date,
                header_fields,
            )
            chunks.extend(section_chunks)

        return chunks

    def _split_at_sections(
        self,
        body_text: str,
        citation: str,
        doc_title: str,
        filename: str,
        effective_date: Optional[str],
        header_fields: Dict[str, str],
    ) -> List[ChunkData]:
        """Split body text at decimal section headers (1.0, 2.0, etc.)."""
        section_matches = list(_SECTION_RE.finditer(body_text))
        chunks: List[ChunkData] = []

        if not section_matches:
            # No section markers found; use semchunk fallback
            sub_chunker = create_sub_chunker(self.max_tokens)
            for j, piece in enumerate(sub_chunker(body_text)):
                chunks.append(
                    ChunkData(
                        text=piece,
                        citation=citation,
                        section_title=doc_title,
                        agency="Seattle DIR",
                        authority_level="local_admin_rule",
                        content_type="substantive",
                        effective_date=effective_date,
                        filename=filename,
                        parent_section=citation,
                        metadata=self._build_metadata(header_fields),
                        subsection_id=f"part{j + 1}",
                    )
                )
            return chunks

        for i, match in enumerate(section_matches):
            section_start = match.start()
            section_end = (
                section_matches[i + 1].start()
                if i + 1 < len(section_matches)
                else len(body_text)
            )

            section_text = body_text[section_start:section_end].strip()
            sec_number = match.group(1)
            sec_title = match.group(2).strip()

            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunks.append(
                    ChunkData(
                        text=section_text,
                        citation=citation,
                        section_title=sec_title,
                        section_number=sec_number,
                        agency="Seattle DIR",
                        authority_level="local_admin_rule",
                        content_type="substantive",
                        effective_date=effective_date,
                        filename=filename,
                        parent_section=citation,
                        metadata=self._build_metadata(header_fields),
                    )
                )
            else:
                # Sub-chunk with semchunk
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(section_text)):
                    chunks.append(
                        ChunkData(
                            text=piece,
                            citation=citation,
                            section_title=sec_title,
                            section_number=sec_number,
                            agency="Seattle DIR",
                            authority_level="local_admin_rule",
                            content_type="substantive",
                            effective_date=effective_date,
                            filename=filename,
                            parent_section=citation,
                            metadata=self._build_metadata(header_fields),
                            subsection_id=f"{sec_number}_part{j + 1}",
                        )
                    )

        return chunks

    @staticmethod
    def _extract_header_fields(text: str) -> Dict[str, str]:
        """Extract structured metadata fields from the header block."""
        fields: Dict[str, str] = {}
        for field_name, pattern in _HEADER_FIELDS.items():
            match = pattern.search(text)
            if match:
                # Strip trailing pipe characters and whitespace from table-formatted values
                value = match.group(1).strip().rstrip("| \t").strip()
                if value and value.lower() not in ("n/a", "na", "none", ""):
                    fields[field_name] = value
        return fields

    @staticmethod
    def _extract_citation(text: str, filename: str = "") -> str:
        """Extract DR XX-YYYY citation from document text with filename fallback.

        Priority logic:
        1. If both body and filename match, prefer filename (body may be a cross-ref).
           If they agree, return the body citation.
        2. If only body matches, return body citation (can't verify against filename).
        3. If only filename matches, return filename citation (fallback for OCR damage).
        4. If neither matches, return empty string.
        """
        # Try body regex
        body_match = _DR_CITATION_RE.search(text)
        body_citation = f"DR {body_match.group(1)}" if body_match else ""

        # Try filename extraction
        fname_citation = ""
        if filename:
            fname = Path(filename).name
            fname_match = _FILENAME_CITATION_RE.match(fname)
            if fname_match:
                fname_citation = f"DR {fname_match.group(1)}"

        # Decision logic
        if body_citation and fname_citation:
            # Both matched — prefer filename (body match could be a cross-reference)
            # If they agree, it doesn't matter which we return
            if body_citation == fname_citation:
                return body_citation
            return fname_citation
        if body_citation:
            return body_citation
        if fname_citation:
            return fname_citation
        return ""

    @staticmethod
    def _build_metadata(header_fields: Dict[str, str]) -> Dict:
        """Build agency-specific metadata dict from header fields."""
        extra: Dict = {}
        field_map = {
            "supersedes": "supersedes",
            "code_reference": "code_reference",
            "ordinance_authority": "ordinance_authority",
            "rule_type": "rule_type",
            "department": "department",
            "publication_date": "publication_date",
        }
        for src_key, dst_key in field_map.items():
            if src_key in header_fields:
                extra[dst_key] = header_fields[src_key]
        return extra
