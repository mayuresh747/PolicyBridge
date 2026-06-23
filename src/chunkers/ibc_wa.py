"""IBC-WA (International Building Code - Washington Amendments) chunking strategy.

Splits IBC-WA amendment documents on WAC section headers (WAC 51-50-XXYY),
detects amendment types (added/amended/deleted/replaced), and handles preface
cross-reference sections as standalone chunks.
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

# Section header: WAC 51-XX-XXXX followed by title (with optional ## markdown prefix)
# Covers all IBC-WA chapters: 51-50 (IBC), 51-51 (IRC), 51-52 (IMC),
# 51-54A (IFC), 51-55 (WUIC), 51-56 (UPC)
_SECTION_RE = re.compile(
    r"^#{0,6}\s*(WAC\s+(51-\d{2,3}[A-Z]?-\d{3,4})\s+(.+?))\s*\.?\s*$",
    re.MULTILINE,
)

# Amendment signal patterns
_AMENDMENT_SIGNALS = {
    "added": re.compile(r"is\s+added", re.IGNORECASE),
    "amended": re.compile(r"is\s+amended", re.IGNORECASE),
    "deleted": re.compile(r"is\s+deleted", re.IGNORECASE),
    "replaced": re.compile(r"replaces", re.IGNORECASE),
}

# Top-level subsection markers for sub-chunking
_SUBSECTION_RE = re.compile(r"^\s*\(\d+\)", re.MULTILINE)

# Statutory Authority block (same as WAC)
_STATUTORY_AUTHORITY_RE = re.compile(
    r"^\[Statutory Authority:.*?(?:\]|$)", re.MULTILINE | re.DOTALL
)

# Energy Code section header: ## SECTION C101 TITLE or ## SECTION A101 TITLE
# Used by complete Energy Code documents (51-11C, 51-11R) which adopt the full IECC
# rather than using individual WAC section headers like amendment documents do.
# Docling may or may not add Markdown heading prefix, so we tolerate both.
_ENERGY_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+)?SECTION\s+([CA]\d{3})\s+(.+)$",
    re.MULTILINE,
)

# Extract WAC chapter number from document header (e.g., "CHAPTER 51-11C WAC")
_WAC_CHAPTER_FROM_HEADER_RE = re.compile(
    r"CHAPTER\s+(51-\d{2,3}[A-Z]*)\s+WAC", re.IGNORECASE
)


class IBCWAChunker(ChunkingStrategy):
    """Chunker for IBC-WA (International Building Code Washington Amendments).

    Splits on WAC 51-50-XXYY section headers, tags amendment types, and
    handles preface/cross-reference sections as standalone chunks.
    """

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split IBC-WA document into section-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        doc_parent = filename.replace(".pdf", "") if filename else "IBC-WA"
        chunks: List[ChunkData] = []

        # Find all WAC section headers
        section_matches = list(_SECTION_RE.finditer(text))

        # Handle preface (text before first WAC section header)
        if section_matches:
            preface_text = text[: section_matches[0].start()].strip()
            if preface_text and len(preface_text) > 50:
                preface_tokens = self._count_tokens(preface_text)
                if preface_tokens <= self.max_tokens:
                    chunks.append(
                        ChunkData(
                            text=preface_text,
                            citation="",
                            section_title="Preface",
                            agency="IBC-WA",
                            authority_level="state_admin_rule",
                            content_type="preface",
                            filename=filename,
                            parent_section=doc_parent,
                            metadata={"base_code": "IBC"},
                        )
                    )
                else:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    for j, piece in enumerate(sub_chunker(preface_text)):
                        chunks.append(
                            ChunkData(
                                text=piece,
                                citation="",
                                section_title=f"Preface (part {j + 1})",
                                agency="IBC-WA",
                                authority_level="state_admin_rule",
                                content_type="preface",
                                filename=filename,
                                parent_section=doc_parent,
                                metadata={"base_code": "IBC"},
                            )
                        )
        elif text.strip():
            # No WAC section headers found — try Energy Code section format
            # (## SECTION C101 TITLE) used by complete adoption documents (51-11C, 51-11R)
            energy_matches = list(_ENERGY_SECTION_RE.finditer(text))
            if energy_matches:
                return self._chunk_energy_code(text, energy_matches, metadata)
            # No recognized section format → semchunk fallback
            return self._fallback_chunk(text.strip(), metadata, authority_level="state_admin_rule")

        # Process each WAC section
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

            # Derive IBC section from last 4 digits of WAC number
            ibc_section = section_number.split("-")[-1]

            # Detect amendment type
            amendment_type = self._detect_amendment_type(section_text)

            extra: Dict = {
                "ibc_section": ibc_section,
                "amendment_type": amendment_type,
                "base_code": "IBC",
            }

            # Check token count
            token_count = self._count_tokens(section_text)

            if token_count <= self.max_tokens:
                chunks.append(
                    ChunkData(
                        text=section_text,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        agency="IBC-WA",
                        authority_level="state_admin_rule",
                        content_type="substantive",
                        filename=filename,
                        parent_section=doc_parent,
                        metadata=extra,
                    )
                )
            else:
                # Sub-chunk at subsection level
                sub_chunks = self._split_at_subsections(
                    section_text,
                    citation,
                    section_title,
                    section_number,
                    filename,
                    extra,
                    doc_parent,
                )
                if sub_chunks:
                    chunks.extend(sub_chunks)
                else:
                    # Last resort: semchunk
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    for j, piece in enumerate(sub_chunker(section_text)):
                        chunks.append(
                            ChunkData(
                                text=piece,
                                citation=citation,
                                section_title=section_title,
                                section_number=section_number,
                                agency="IBC-WA",
                                authority_level="state_admin_rule",
                                content_type="substantive",
                                filename=filename,
                                parent_section=doc_parent,
                                metadata=extra,
                                subsection_id=f"{section_number}_part{j + 1}",
                            )
                        )

        return chunks

    def _chunk_energy_code(
        self,
        text: str,
        section_matches: list,
        metadata: Dict,
    ) -> List[ChunkData]:
        """Process Energy Code documents (51-11C/51-11R) that use SECTION CXxx headers.

        These are complete code adoption documents, not WAC amendment overlays.
        Citation format: "WAC 51-11C §C101"
        """
        filename = metadata.get("filename", "")
        doc_parent = filename.replace(".pdf", "") if filename else "IBC-WA"

        # Extract WAC chapter from document header (first 1000 chars)
        chapter_match = _WAC_CHAPTER_FROM_HEADER_RE.search(text[:1000])
        wac_chapter = chapter_match.group(1) if chapter_match else "51-11C"

        chunks: List[ChunkData] = []

        # Preamble (before first energy section)
        preface_text = text[: section_matches[0].start()].strip()
        if preface_text and len(preface_text) > 50:
            if self._count_tokens(preface_text) <= self.max_tokens:
                chunks.append(ChunkData(
                    text=preface_text,
                    citation=f"WAC {wac_chapter}",
                    section_title="Preface",
                    agency="IBC-WA",
                    authority_level="state_admin_rule",
                    content_type="preface",
                    filename=filename,
                    parent_section=doc_parent,
                ))
            else:
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(preface_text)):
                    chunks.append(ChunkData(
                        text=piece,
                        citation=f"WAC {wac_chapter}",
                        section_title=f"Preface (part {j + 1})",
                        agency="IBC-WA",
                        authority_level="state_admin_rule",
                        content_type="preface",
                        filename=filename,
                        parent_section=doc_parent,
                    ))

        # Process each energy code section
        for i, match in enumerate(section_matches):
            section_start = match.start()
            section_end = (
                section_matches[i + 1].start()
                if i + 1 < len(section_matches)
                else len(text)
            )
            section_text = text[section_start:section_end].strip()
            section_number = match.group(1)          # e.g. "C101"
            section_title = match.group(2).strip()   # e.g. "SCOPE AND GENERAL REQUIREMENTS"
            citation = f"WAC {wac_chapter} §{section_number}"

            if self._count_tokens(section_text) <= self.max_tokens:
                chunks.append(ChunkData(
                    text=section_text,
                    citation=citation,
                    section_title=section_title,
                    section_number=section_number,
                    agency="IBC-WA",
                    authority_level="state_admin_rule",
                    content_type="substantive",
                    filename=filename,
                    parent_section=doc_parent,
                    metadata={"wac_chapter": wac_chapter},
                ))
            else:
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(section_text)):
                    chunks.append(ChunkData(
                        text=piece,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        agency="IBC-WA",
                        authority_level="state_admin_rule",
                        content_type="substantive",
                        filename=filename,
                        parent_section=doc_parent,
                        metadata={"wac_chapter": wac_chapter},
                        subsection_id=f"{section_number}_part{j + 1}",
                    ))

        return chunks

    def _split_at_subsections(
        self,
        section_text: str,
        citation: str,
        section_title: str,
        section_number: str,
        filename: str,
        extra: Dict,
        doc_parent: str = "",
    ) -> List[ChunkData] | None:
        """Try splitting at (1), (2) subsection boundaries."""
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
                    chunks.append(
                        ChunkData(
                            text=piece,
                            citation=citation,
                            section_title=section_title,
                            section_number=section_number,
                            agency="IBC-WA",
                            authority_level="state_admin_rule",
                            content_type="substantive",
                            filename=filename,
                            parent_section=doc_parent or None,
                            metadata=extra,
                            subsection_id=f"{section_number}({k + 1})_part{j + 1}",
                        )
                    )
            else:
                chunks.append(
                    ChunkData(
                        text=sub_text,
                        citation=citation,
                        section_title=section_title,
                        section_number=section_number,
                        agency="IBC-WA",
                        authority_level="state_admin_rule",
                        content_type="substantive",
                        filename=filename,
                        parent_section=doc_parent or None,
                        metadata=extra,
                        subsection_id=f"{section_number}({k + 1})",
                    )
                )

        return chunks if chunks else None

    @staticmethod
    def _detect_amendment_type(section_text: str) -> str:
        """Detect the amendment type from section text."""
        # Check first ~500 chars for amendment signals
        header_area = section_text[:500]
        for atype, pattern in _AMENDMENT_SIGNALS.items():
            if pattern.search(header_area):
                return atype
        return "amended"  # Default if no signal found
