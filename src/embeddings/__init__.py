"""Embedding pipeline for the Seattle Regulatory RAG ingestion system."""

from src.embeddings.openai_embedder import (
    OpenAIEmbedder,
    embed_and_store,
    embed_texts_sync,
)

__all__ = [
    "OpenAIEmbedder",
    "embed_texts_sync",
    "embed_and_store",
]
