"""Knowledge graph construction for the Seattle Regulatory RAG system.

Modules:
    citation_index: Build and query the citation-to-chunk-ID lookup index.
    extractor: Rule-based relationship extraction (6 deterministic types).
    llm_extractor: LLM-based relationship extraction (GPT-4.1-mini, primary).
    kuzu_writer: Kuzu graph DB schema, bulk loading, and queries.
    conflict_adjudicator: CONFLICTS_WITH candidate generation and LLM adjudicator.
"""

from src.graph.citation_index import (
    build_citation_index,
    normalize_citation,
    resolve_citation,
)
from src.graph.conflict_adjudicator import (
    ConflictResult,
    adjudicate_conflicts,
    generate_conflict_candidates,
)
from src.graph.extractor import (
    Relationship,
    extract_all_relationships,
    extract_next_section_edges,
    IMPLEMENTS_PATTERNS,
    SUBJECT_TO_PATTERNS,
    DEFINED_BY_PATTERNS,
    AMENDED_BY_PATTERNS,
)
from src.graph.llm_extractor import extract_relationships_llm
from src.graph.kuzu_writer import KuzuWriter

__all__ = [
    "build_citation_index",
    "normalize_citation",
    "resolve_citation",
    "ConflictResult",
    "adjudicate_conflicts",
    "generate_conflict_candidates",
    "Relationship",
    "extract_all_relationships",
    "extract_next_section_edges",
    "extract_relationships_llm",
    "IMPLEMENTS_PATTERNS",
    "SUBJECT_TO_PATTERNS",
    "DEFINED_BY_PATTERNS",
    "AMENDED_BY_PATTERNS",
    "KuzuWriter",
]
