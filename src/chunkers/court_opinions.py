"""WA Court Opinions chunking strategy.

Splits court opinion documents at ALL-CAPS section headings (FACTS, ANALYSIS,
CONCLUSION), discards page 1 slip opinion notice, extracts case caption
metadata, sub-chunks ANALYSIS at A./B. level, merges short sections, and
tags concurrence/dissent sections.
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

# ALL-CAPS section headings (4+ chars, entire line is uppercase)
# Docling may render some headings as Markdown (## ANALYSIS), so we allow
# an optional #{1,6} prefix before the ALL-CAPS text.
_HEADING_RE = re.compile(r"^(?:#{1,6}\s+)?([A-Z][A-Z\s]{3,})$", re.MULTILINE)

# Lettered subsection markers for ANALYSIS sub-chunking
_LETTER_SUBSECTION_RE = re.compile(r"^\s*[A-Z]\.\s+", re.MULTILINE)

# Slip opinion notice detection (page 1 boilerplate)
_SLIP_NOTICE_RE = re.compile(
    r"This opinion was filed for record", re.IGNORECASE
)
_IN_THE_RE = re.compile(
    r"^IN THE\b", re.MULTILINE
)

# Caption parsing patterns
_CASE_NUMBER_RE = re.compile(r"No\.\s+(\d{5,}-\d)")
_FILING_DATE_RE = re.compile(
    r"[Ff]iled\s+(\w+\s+\d{1,2},\s+\d{4})"
)
_AUTHOR_JUSTICE_RE = re.compile(r"^(\w+),\s+J\.", re.MULTILINE)
_COURT_RE = re.compile(
    r"(SUPREME COURT|COURT OF APPEALS.*?DIVISION\s+[IV]+)",
    re.IGNORECASE,
)
_PARTIES_RE = re.compile(
    r"^(.+?)\s*,\s*$\s*(?:Appellant|Respondent|Petitioner|Plaintiff|Defendant)",
    re.MULTILINE,
)

# Concurrence/dissent detection
_CONCURRENCE_RE = re.compile(
    r"\b(?:concurring|concurrence)\b", re.IGNORECASE
)
_DISSENT_RE = re.compile(
    r"\b(?:dissenting|dissent)\b", re.IGNORECASE
)

# Minimum token threshold for short section merging
_MIN_SECTION_TOKENS = 200


class CourtOpinionChunker(ChunkingStrategy):
    """Chunker for Washington State Court Opinion documents.

    Handles slip opinion page 1 discard, case caption extraction,
    ALL-CAPS section splitting, ANALYSIS sub-chunking at A./B. level,
    short section merging, and concurrence/dissent tagging.

    Default max_tokens is 3000 (court opinions need larger chunks for
    legal reasoning context).
    """

    def __init__(self, max_tokens: int = 3000):
        super().__init__(max_tokens=max_tokens)

    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split court opinion document into section-level chunks.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects.
        """
        filename = metadata.get("filename", "")
        chunks: List[ChunkData] = []

        # Phase 1: Discard page 1 slip opinion notice
        text = self._discard_slip_notice(text)

        # Phase 2: Extract case caption metadata
        caption_info = self._extract_caption(text)
        case_citation = self._build_citation(caption_info, filename)

        # Try to find a proper "X v. Y" format citation from the text body
        text_citations = extract_citations(text[:3000])
        wa_case_cites = [c for c in text_citations if " v. " in c]
        if wa_case_cites:
            case_citation = wa_case_cites[0]

        # Create caption metadata chunk
        caption_text = self._extract_caption_text(text)
        if caption_text:
            chunks.append(
                ChunkData(
                    text=caption_text,
                    citation=case_citation,
                    section_title="Case Caption",
                    agency="WA Court Opinions",
                    authority_level="court_opinion",
                    content_type="case_caption",
                    filename=filename,
                    parent_section=case_citation,
                    metadata=caption_info,
                )
            )

        # Phase 3: Split at ALL-CAPS section headings
        headings = list(_HEADING_RE.finditer(text))

        if not headings:
            # No ALL-CAPS headings found — use fallback chunker to prevent
            # returning a single oversized chunk for long unstructured opinions
            if text.strip():
                fallback = self._fallback_chunk(
                    text.strip(), metadata, authority_level="court_opinion"
                )
                for c in fallback:
                    c.citation = case_citation
                    c.section_title = case_citation
                    c.parent_section = case_citation
                chunks.extend(fallback)
            return chunks

        # Build sections from headings
        sections: List[tuple[str, str]] = []  # (heading_text, section_body)
        for i, heading_match in enumerate(headings):
            heading_text = heading_match.group(1).strip()
            section_start = heading_match.start()
            section_end = (
                headings[i + 1].start()
                if i + 1 < len(headings)
                else len(text)
            )
            section_body = text[section_start:section_end].strip()
            sections.append((heading_text, section_body))

        # Phase 5: Merge short sections with the next section
        merged_sections = self._merge_short_sections(sections)

        # Phase 4 & 6: Process each section
        for heading_text, section_body in merged_sections:
            # Detect opinion type for concurrence/dissent sections
            opinion_type = self._detect_opinion_type(heading_text)

            extra = dict(caption_info)
            extra["opinion_type"] = opinion_type

            token_count = self._count_tokens(section_body)

            # Phase 4: Sub-chunk ANALYSIS at A., B. level if oversized
            is_analysis = "ANALYSIS" in heading_text.upper()

            if token_count <= self.max_tokens:
                chunks.append(
                    ChunkData(
                        text=section_body,
                        citation=case_citation,
                        section_title=heading_text,
                        agency="WA Court Opinions",
                        authority_level="court_opinion",
                        content_type="substantive",
                        filename=filename,
                        parent_section=case_citation,
                        metadata=extra,
                    )
                )
            elif is_analysis:
                # Try sub-chunking at A., B. level for ANALYSIS
                sub_chunks = self._split_at_letter_subsections(
                    section_body,
                    case_citation,
                    heading_text,
                    filename,
                    extra,
                )
                if sub_chunks:
                    chunks.extend(sub_chunks)
                else:
                    # Last resort: semchunk
                    sub_chunker = create_sub_chunker(self.max_tokens)
                    for j, piece in enumerate(sub_chunker(section_body)):
                        sub_extra = dict(extra)
                        chunks.append(
                            ChunkData(
                                text=piece,
                                citation=case_citation,
                                section_title=f"{heading_text} (part {j + 1})",
                                agency="WA Court Opinions",
                                authority_level="court_opinion",
                                content_type="substantive",
                                filename=filename,
                                parent_section=case_citation,
                                metadata=sub_extra,
                            )
                        )
            else:
                # Non-ANALYSIS oversized section: use semchunk
                sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(section_body)):
                    chunks.append(
                        ChunkData(
                            text=piece,
                            citation=case_citation,
                            section_title=f"{heading_text} (part {j + 1})",
                            agency="WA Court Opinions",
                            authority_level="court_opinion",
                            content_type="substantive",
                            filename=filename,
                            parent_section=case_citation,
                            metadata=extra,
                        )
                    )

        return chunks

    def _split_at_letter_subsections(
        self,
        section_text: str,
        citation: str,
        heading: str,
        filename: str,
        extra: Dict,
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
            sub_extra = dict(extra)
            if self._count_tokens(sub_text) > self.max_tokens:
                if sub_chunker is None:
                    sub_chunker = create_sub_chunker(self.max_tokens)
                for j, piece in enumerate(sub_chunker(sub_text)):
                    chunks.append(
                        ChunkData(
                            text=piece,
                            citation=citation,
                            section_title=f"{heading} ({chr(65 + k)}., part {j + 1})",
                            agency="WA Court Opinions",
                            authority_level="court_opinion",
                            content_type="substantive",
                            filename=filename,
                            parent_section=citation,
                            metadata=sub_extra,
                        )
                    )
            else:
                chunks.append(
                    ChunkData(
                        text=sub_text,
                        citation=citation,
                        section_title=f"{heading} ({chr(65 + k)}.)",
                        agency="WA Court Opinions",
                        authority_level="court_opinion",
                        content_type="substantive",
                        filename=filename,
                        parent_section=citation,
                        metadata=sub_extra,
                    )
                )

        return chunks if chunks else None

    @staticmethod
    def _discard_slip_notice(text: str) -> str:
        """Discard page 1 slip opinion notice boilerplate."""
        # Look for "This opinion was filed for record" or "IN THE" pattern
        slip_match = _SLIP_NOTICE_RE.search(text)
        if slip_match:
            # Find the end of the slip notice section
            in_the = _IN_THE_RE.search(text[slip_match.end() :])
            if in_the:
                return text[slip_match.end() + in_the.start() :]

        # Alternative: look for IN THE as start of real content
        in_the_direct = _IN_THE_RE.search(text)
        if in_the_direct and in_the_direct.start() > 100:
            return text[in_the_direct.start() :]

        return text

    @staticmethod
    def _extract_caption(text: str) -> Dict:
        """Extract case caption metadata from the beginning of the document."""
        caption: Dict = {}

        case_num = _CASE_NUMBER_RE.search(text[:2000])
        if case_num:
            caption["case_number"] = case_num.group(1)

        filing_date = _FILING_DATE_RE.search(text[:2000])
        if filing_date:
            caption["filing_date"] = filing_date.group(1)

        author = _AUTHOR_JUSTICE_RE.search(text[:2000])
        if author:
            caption["author_justice"] = author.group(1)

        court = _COURT_RE.search(text[:2000])
        if court:
            court_text = court.group(1).strip()
            if "SUPREME" in court_text.upper():
                caption["court"] = "WA Supreme Court"
            elif "APPEALS" in court_text.upper():
                caption["court"] = f"WA Court of Appeals {court_text.split('DIVISION')[-1].strip() if 'DIVISION' in court_text.upper() else ''}"
            else:
                caption["court"] = court_text

        # Extract parties
        caption["opinion_type"] = "majority"

        return caption

    @staticmethod
    def _extract_caption_text(text: str) -> Optional[str]:
        """Extract the caption text block from the beginning of the opinion."""
        # Caption is from start to first ALL-CAPS heading
        first_heading = _HEADING_RE.search(text)
        if first_heading and first_heading.start() > 50:
            caption_text = text[: first_heading.start()].strip()
            if len(caption_text) > 30:
                return caption_text
        return None

    @staticmethod
    def _build_citation(caption_info: Dict, filename: str) -> str:
        """Build a citation string from caption info or filename."""
        # Try to build from parties if available
        # Fall back to filename-based citation
        case_num = caption_info.get("case_number", "")
        if case_num:
            return f"No. {case_num}"
        # Use filename as fallback
        if filename:
            name = filename.replace(".pdf", "").replace("_", " ")
            return name
        return ""

    def _merge_short_sections(
        self, sections: List[tuple[str, str]]
    ) -> List[tuple[str, str]]:
        """Merge sections shorter than _MIN_SECTION_TOKENS with the next section."""
        if not sections:
            return sections

        merged: List[tuple[str, str]] = []
        carry_heading = ""
        carry_body = ""

        for heading, body in sections:
            if carry_body:
                # Append carried-over content to current section
                combined_body = carry_body + "\n\n" + body
                combined_heading = carry_heading
                carry_body = ""
                carry_heading = ""

                if self._count_tokens(combined_body) < _MIN_SECTION_TOKENS:
                    carry_heading = combined_heading
                    carry_body = combined_body
                else:
                    merged.append((combined_heading, combined_body))
            elif self._count_tokens(body) < _MIN_SECTION_TOKENS:
                carry_heading = heading
                carry_body = body
            else:
                merged.append((heading, body))

        # Handle any remaining carried content
        if carry_body:
            if merged:
                # Merge with last section
                last_heading, last_body = merged[-1]
                merged[-1] = (last_heading, last_body + "\n\n" + carry_body)
            else:
                merged.append((carry_heading, carry_body))

        return merged

    @staticmethod
    def _detect_opinion_type(heading_text: str) -> str:
        """Detect if a section is a concurrence or dissent."""
        if _CONCURRENCE_RE.search(heading_text):
            return "concurrence"
        if _DISSENT_RE.search(heading_text):
            return "dissent"
        return "majority"
