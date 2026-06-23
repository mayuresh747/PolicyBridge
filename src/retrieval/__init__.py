"""Retrieval engine for the Seattle Regulatory RAG system.

Provides hybrid retrieval (vector + BM25 + graph + RRF fusion) and the
RetrievalResult contract dataclass used by Phase 4 (chat agent).

Public API:
    retrieve() -- main entry point for hybrid retrieval
    RetrievalResult -- dataclass for retrieval results
"""

from src.retrieval.conflict_expander import expand_conflicts
from src.retrieval.hybrid import retrieve
from src.retrieval.models import RetrievalResult

__all__ = ["expand_conflicts", "retrieve", "RetrievalResult"]
