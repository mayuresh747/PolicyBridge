"""Per-agency chunking strategies for Seattle regulatory document processing.

Each agency has a self-contained chunker with its own citation regex, section
boundary detection, metadata extraction, and sub-chunking rules. The
get_chunker() factory returns the correct chunker for a given agency name.
"""

from src.chunkers.base import (
    CITATION_PATTERNS,
    ChunkData,
    ChunkingStrategy,
    extract_citations,
    get_chunker,
)
from src.chunkers.court_opinions import CourtOpinionChunker
from src.chunkers.dir import DirectorRuleChunker
from src.chunkers.governor_orders import GovernorOrderChunker
from src.chunkers.ibc_wa import IBCWAChunker
from src.chunkers.rcw import RCWChunker
from src.chunkers.smc import SMCChunker
from src.chunkers.spu import SPUChunker
from src.chunkers.wac import WACChunker

__all__ = [
    "ChunkData",
    "ChunkingStrategy",
    "get_chunker",
    "extract_citations",
    "CITATION_PATTERNS",
    "WACChunker",
    "RCWChunker",
    "SMCChunker",
    "DirectorRuleChunker",
    "IBCWAChunker",
    "SPUChunker",
    "CourtOpinionChunker",
    "GovernorOrderChunker",
]
