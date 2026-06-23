"""Data models for the retrieval engine.

RetrievalResult is the Phase 4 contract — every retrieval path (vector, BM25,
graph, hybrid) must produce results conforming to this dataclass.
"""

from dataclasses import dataclass, field


@dataclass
class RetrievalResult:
    """A single retrieval result with fused score and full citation metadata.

    This is the contract between Phase 3 (Retrieval Engine) and Phase 4
    (Chat Agent).  All 11 fields are defined per decision D-13.

    Attributes:
        chunk_id: Unique identifier for the chunk in LanceDB.
        text: The full text content of the chunk.
        score: Fused RRF score (higher = more relevant).
        citation: Human-readable citation string (e.g., "RCW 36.70A.681").
        section_title: Title of the section, if available.
        agency: Source agency code (e.g., "RCW", "SMC", "WAC").
        authority_level: Legal authority classification (e.g., "state_statute").
        document_type: Document classification (e.g., "substantive", "procedural").
        retrieval_sources: Which retrieval methods found this chunk
            (e.g., ["vector", "bm25", "graph"]).
        graph_context: Related chunks discovered via graph traversal, or None.
        citation_path: Structured citation with keys: agency, document, section,
            subsection.  Defaults to empty dict.
    """

    chunk_id: str
    text: str
    score: float
    citation: str
    section_title: str | None
    agency: str
    authority_level: str
    document_type: str
    retrieval_sources: list[str] = field(default_factory=list)
    graph_context: list[dict] | None = None
    citation_path: dict = field(default_factory=dict)
