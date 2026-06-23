"""Async OpenAI embedding client for the Seattle Regulatory RAG ingestion pipeline.

OpenAIEmbedder: batched async embedding with rate limiting, retry logic, and
cost tracking using text-embedding-3-large (3072-dim).

embed_texts_sync: synchronous wrapper for non-async contexts.
embed_and_store: bridges chunking output to LanceDB storage via the embedder.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, List

from openai import AsyncOpenAI, RateLimitError

from src.config import (
    EMBED_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MAX_CONCURRENT_EMBEDS,
)

if TYPE_CHECKING:
    from src.chunkers.base import ChunkData
    from src.storage.lancedb_writer import LanceDBWriter

logger = logging.getLogger(__name__)

# Cost per 1M tokens for text-embedding-3-large (as of 2025)
_COST_PER_MILLION_TOKENS = 0.13


class OpenAIEmbedder:
    """Async OpenAI embedding client with batching, concurrency control, and cost tracking.

    Usage::

        embedder = OpenAIEmbedder()
        vectors = await embedder.embed_texts(["hello world", "regulatory text"])
        print(embedder.get_cost_summary())
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        batch_size: int = EMBED_BATCH_SIZE,
        max_concurrent: int = MAX_CONCURRENT_EMBEDS,
        max_retries: int = 5,
    ):
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._client: AsyncOpenAI | None = None  # Lazy-initialized
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Cost tracking
        self.total_tokens_used = 0
        self.total_api_calls = 0
        self.total_cost_usd = 0.0

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-initialized AsyncOpenAI client.

        Defers client creation until first use so that the class can be
        instantiated without ``OPENAI_API_KEY`` being set (useful for
        testing and import verification).
        """
        if self._client is None:
            self._client = AsyncOpenAI()  # Uses OPENAI_API_KEY from environment
        return self._client

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts, automatically batching into groups of batch_size.

        Splits the input into batches of ``self.batch_size`` (default 100),
        dispatches them concurrently (up to ``max_concurrent`` at a time via
        the semaphore), and concatenates results in order.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of ``self.dimensions`` floats).
        """
        if not texts:
            return []

        # Split into batches
        batches = [
            texts[i : i + self.batch_size]
            for i in range(0, len(texts), self.batch_size)
        ]

        # Run all batches concurrently (semaphore limits actual concurrency)
        tasks = [self._embed_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        # Flatten results in order
        all_embeddings: List[List[float]] = []
        for result in batch_results:
            all_embeddings.extend(result)

        # Update cumulative cost
        self.total_cost_usd = self.total_tokens_used / 1_000_000 * _COST_PER_MILLION_TOKENS

        return all_embeddings

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a single batch with retry and rate limit handling.

        Uses exponential backoff with jitter on RateLimitError (429).

        Args:
            texts: A single batch of texts (length <= batch_size).

        Returns:
            List of embedding vectors for this batch.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        for attempt in range(self.max_retries):
            try:
                async with self.semaphore:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=texts,
                        dimensions=self.dimensions,
                    )
                    self.total_tokens_used += response.usage.total_tokens
                    self.total_api_calls += 1
                    return [item.embedding for item in response.data]
            except RateLimitError:
                # Exponential backoff with jitter
                wait = (2 ** attempt) + (random.random() * 0.5)
                logger.warning(
                    "Rate limited (attempt %d/%d), waiting %.1fs",
                    attempt + 1,
                    self.max_retries,
                    wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"Embedding failed after {self.max_retries} retries"
        )

    def get_cost_summary(self) -> dict:
        """Return cost tracking summary.

        Returns:
            Dict with ``total_tokens_used``, ``total_api_calls``, and
            ``estimated_cost_usd`` (at $0.13 per 1M tokens for
            text-embedding-3-large).
        """
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_api_calls": self.total_api_calls,
            "estimated_cost_usd": round(
                self.total_tokens_used / 1_000_000 * _COST_PER_MILLION_TOKENS, 6
            ),
        }


def embed_texts_sync(texts: List[str], **kwargs) -> List[List[float]]:
    """Synchronous wrapper around ``OpenAIEmbedder.embed_texts()``.

    Creates a new ``OpenAIEmbedder`` instance, runs the async embed loop,
    and returns results.  Useful in non-async contexts (scripts, notebooks).

    Args:
        texts: List of text strings to embed.
        **kwargs: Forwarded to ``OpenAIEmbedder.__init__()``.

    Returns:
        List of embedding vectors.
    """
    embedder = OpenAIEmbedder(**kwargs)
    return asyncio.run(embedder.embed_texts(texts))


async def embed_and_store(
    chunks: List["ChunkData"],
    embedder: OpenAIEmbedder,
    writer: "LanceDBWriter",
    batch_size: int = 1000,
) -> int:
    """Embed chunks in batches and write to LanceDB.

    Processes chunks in groups of ``batch_size`` (default 1000):

    1. Extract text from each ``ChunkData``
    2. Call ``embedder.embed_texts()`` on the batch
    3. Call ``writer.write_batch()`` with chunks + embeddings
    4. Return total number of chunks stored

    This function bridges the chunking pipeline output to LanceDB storage,
    handling the embedding step in between.

    Args:
        chunks: List of ``ChunkData`` objects (no embeddings yet).
        embedder: Configured ``OpenAIEmbedder`` instance.
        writer: Configured ``LanceDBWriter`` instance (table already created).
        batch_size: Number of chunks to embed and store per iteration.

    Returns:
        Total number of chunks successfully stored.
    """
    from src.chunkers.base import ChunkData as _ChunkData  # noqa: F811
    from src.storage.lancedb_writer import LanceDBWriter as _LanceDBWriter  # noqa: F811

    total_stored = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        embeddings = await embedder.embed_texts(texts)
        stored = writer.write_batch(batch, embeddings)
        total_stored += stored
        logger.info(
            "Embedded and stored batch %d-%d (%d chunks)",
            i,
            i + len(batch),
            stored,
        )
    return total_stored
