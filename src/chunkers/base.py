"""Base chunking abstractions for the Seattle Regulatory RAG ingestion pipeline.

ChunkData: lightweight, picklable dataclass for inter-process chunk transfer.
ChunkingStrategy: abstract base class for per-agency chunking implementations.
CITATION_PATTERNS: compiled regex patterns for cross-agency citation extraction.
extract_citations: runs all citation patterns against text, returns deduplicated matches.
create_sub_chunker: creates a semchunk-based sub-chunker as last-resort fallback.
get_chunker: factory function that returns the correct chunker for a given agency.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ChunkData:
    """Lightweight, picklable chunk representation for inter-process transfer.

    Uses a plain dataclass (not Pydantic) so it can be serialized via pickle
    across multiprocessing boundaries without issues.
    """

    text: str
    citation: str
    section_title: str
    agency: str
    authority_level: str
    content_type: Optional[str] = None
    is_table: bool = False
    table_type: Optional[str] = None
    filename: str = ""
    section_number: Optional[str] = None
    subsection_id: Optional[str] = None
    jurisdiction: str = "washington"
    effective_date: Optional[str] = None
    last_amended_date: Optional[str] = None
    parent_section: Optional[str] = None
    is_scanned: bool = False
    ocr_confidence: Optional[float] = None
    key_terms: Optional[str] = None  # JSON-serialized list
    metadata: dict = field(default_factory=dict)  # Agency-specific extra fields
    chunk_index: int = 0  # Ordinal position within document (set by pipeline)
    has_images: bool = False  # True if source page contained images
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Text normalization (applied before chunking)
# ---------------------------------------------------------------------------

_IMAGE_ARTIFACT_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)
_UNKNOWN_ARTIFACT_RE = re.compile(r"<unknown>")
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")


def normalize_text(text: str) -> str:
    """Clean raw Docling markdown for embedding quality.

    Strips image artifacts, excessive whitespace, zero-width characters,
    and other conversion residue.
    """
    text = _IMAGE_ARTIFACT_RE.sub("", text)
    text = _UNKNOWN_ARTIFACT_RE.sub("", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)
    return text.strip()


# Minimum chunk size — chunks below this are garbage (stubs, headers, image-only pages)
MIN_CHUNK_TOKENS = 20


# ---------------------------------------------------------------------------
# Cross-agency citation regex patterns (compiled for performance)
# Source: .planning/research/CHUNKING_STRATEGIES.md — Cross-Agency Citation Regex
# ---------------------------------------------------------------------------

CITATION_PATTERNS = {
    "rcw": re.compile(
        r"RCW\s+(\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4}(?:\(\d+\))*(?:\([a-z]\))*)"
    ),
    "rcw_chapter": re.compile(
        r"(?:chapter|Chapter)\s+(\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?)\s+RCW"
    ),
    "wac": re.compile(
        r"WAC\s+(\d{2,3}-\d{2,3}[A-Z]?-\d{3,5}(?:\(\d+\))*(?:\([a-z]\))*)"
    ),
    "smc": re.compile(
        r"SMC\s+(\d{1,2}\.\d{2,3}\.\d{3}(?:\([A-Za-z]\))*)"
    ),
    "smc_section": re.compile(
        r"Section\s+(\d{1,2}\.\d{2,3}\.\d{3})"
    ),
    "dir": re.compile(
        r"(?:DR|Director'?s?\s+Rule)\s+(\d{1,2}-\d{4})"
    ),
    "eo": re.compile(
        r"(?:Executive Order|EO)\s+(\d{2}-\d{2})"
    ),
    "ibc": re.compile(
        r"IBC\s+(?:Section\s+)?(\d{3,4}(?:\.\d+)*)"
    ),
    "wa_case": re.compile(
        r"(\w+(?:\s+\w+)?)\s+v\.\s+(\w+(?:\s+\w+)?),\s+(\d+)\s+Wn\.(?:2d|App\.)\s+(\d+)"
    ),
    "wa_const": re.compile(
        r"WASH\.\s+CONST\.\s+art\.\s+([IVXLC]+),\s+(?:section|§)\s+(\d+)"
    ),
    "ordinance": re.compile(
        r"Ord\.\s+(\d{6})"
    ),
}


# Pattern for bare section numbers following an RCW-prefixed citation in a
# comma-separated list.  Matches sequences like:
#   "RCW 62A.9A-406, 62A.9A-407, 62A.9A-408, and 62A.9A-409"
# The first element is captured by CITATION_PATTERNS["rcw"]; this pattern
# captures the trailing bare references and re-attaches the "RCW " prefix.
_RCW_LIST_RE = re.compile(
    r"RCW\s+\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4}(?:\([^)]*\))*"
    r"((?:,\s*(?:and\s+)?"
    r"\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4}(?:\([^)]*\))*)+)"
)
_BARE_RCW_NUM_RE = re.compile(
    r"(\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?[.-]\d{3,4}(?:\([^)]*\))*)"
)


def extract_citations(text: str) -> List[str]:
    """Run all CITATION_PATTERNS against text, return deduplicated citation strings.

    Returns the full matched substring (not just the captured group) so that
    citations are human-readable (e.g., "RCW 36.70A.681", not just "36.70A.681").

    Also captures bare section numbers in comma-separated lists following an
    RCW-prefixed citation (e.g., ``62A.9A-407`` in ``RCW 62A.9A-406,
    62A.9A-407``) and returns them with the ``RCW`` prefix re-attached.
    """
    seen: set[str] = set()
    results: List[str] = []
    for _name, pattern in CITATION_PATTERNS.items():
        for match in pattern.finditer(text):
            full = match.group(0)
            if full not in seen:
                seen.add(full)
                results.append(full)

    # Capture bare RCW section numbers in comma-separated lists
    for m in _RCW_LIST_RE.finditer(text):
        trailing = m.group(1)
        for bare_m in _BARE_RCW_NUM_RE.finditer(trailing):
            rcw_citation = f"RCW {bare_m.group(1)}"
            if rcw_citation not in seen:
                seen.add(rcw_citation)
                results.append(rcw_citation)

    return results


def create_sub_chunker(max_tokens: int):
    """Create a semchunk-based sub-chunker as last-resort fallback.

    Uses tiktoken cl100k_base encoding (same as text-embedding-3-large) to
    ensure token counts are consistent with the embedding model.

    Returns:
        A callable that accepts a string and returns a list of sub-chunks.
    """
    import semchunk
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    return semchunk.chunkerify(enc, chunk_size=max_tokens)


class ChunkingStrategy(ABC):
    """Abstract base class for per-agency chunking strategies.

    Each agency implements its own subclass with regex-based section detection,
    metadata extraction, and sub-chunking logic. semchunk is used as a fallback
    when a section exceeds max_tokens or when the primary regex produces no splits.
    """

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens

    @abstractmethod
    def chunk(
        self, text: str, tables: List[str], metadata: Dict
    ) -> List[ChunkData]:
        """Split document text into chunks with metadata.

        Args:
            text: Full document text (Markdown from Docling export).
            tables: List of table strings in Markdown format.
            metadata: Dict with at minimum 'filename' and 'agency' keys.

        Returns:
            List of ChunkData objects, each with chunk_index=0 (set by pipeline).
        """
        pass

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken cl100k_base encoding.

        This encoding is used by GPT-4 and text-embedding-3-large, ensuring
        chunk sizes are accurate relative to the embedding model's tokenization.
        """
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    def _fallback_chunk(
        self, text: str, metadata: Dict, authority_level: str = ""
    ) -> List[ChunkData]:
        """Semchunk fallback for documents where the primary regex produces no splits
        or produces a single chunk that exceeds 3x max_tokens.

        Creates chunks tagged with content_type='fallback' so they are identifiable.
        Garbage chunks below MIN_CHUNK_TOKENS are filtered out.

        Args:
            authority_level: The agency-specific authority level (e.g. 'state_statute').
                             Callers should pass this so metadata completeness is tracked.
        """
        sub_chunker = create_sub_chunker(self.max_tokens)
        parts = sub_chunker(text)
        chunks = []
        for part in parts:
            part = part.strip()
            if not part or self._count_tokens(part) < MIN_CHUNK_TOKENS:
                continue
            chunks.append(ChunkData(
                text=part,
                citation="",
                section_title="",
                agency=metadata.get("agency", ""),
                authority_level=authority_level,
                content_type="fallback",
                filename=metadata.get("filename", ""),
                is_scanned=metadata.get("is_scanned", False),
                ocr_confidence=metadata.get("ocr_confidence"),
            ))
        return chunks

    def _has_image_artifacts(self, text: str) -> bool:
        """Return True if the original text contained image placeholders."""
        return bool(_IMAGE_ARTIFACT_RE.search(text))


def get_chunker(agency: str) -> ChunkingStrategy:
    """Factory function that returns the correct ChunkingStrategy for a given agency.

    Args:
        agency: One of the 8 agency keys from AGENCY_FOLDERS config.

    Returns:
        An instance of the agency-specific ChunkingStrategy subclass.

    Raises:
        ValueError: If the agency name is not recognized.
    """
    from src.chunkers.wac import WACChunker
    from src.chunkers.rcw import RCWChunker
    from src.chunkers.smc import SMCChunker
    from src.chunkers.dir import DirectorRuleChunker
    from src.chunkers.ibc_wa import IBCWAChunker
    from src.chunkers.spu import SPUChunker
    from src.chunkers.court_opinions import CourtOpinionChunker
    from src.chunkers.governor_orders import GovernorOrderChunker
    from src.config import CHUNK_SIZE_LIMITS

    chunkers = {
        "WAC": WACChunker,
        "RCW": RCWChunker,
        "SMC": SMCChunker,
        "Seattle DIR": DirectorRuleChunker,
        "IBC-WA": IBCWAChunker,
        "SPU": SPUChunker,
        "WA Court Opinions": CourtOpinionChunker,
        "Governor Orders": GovernorOrderChunker,
    }
    if agency not in chunkers:
        raise ValueError(
            f"Unknown agency: '{agency}'. Valid: {list(chunkers.keys())}"
        )
    return chunkers[agency](max_tokens=CHUNK_SIZE_LIMITS[agency])
