"""Shared async LLM call manager with semaphore, retry, and rate limit handling.

Adapted from src/graph/llm_extractor.py pattern. Provides a single
LLMCallManager instance for all Phase 4 pipeline stages (classifier,
decomposer, premise detector, synthesizer).

FALLBACK: This file may be created by parallel Plan 04-01 agent.
Defines locally for Plan 04-04 if not yet available.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)


class LLMCallManager:
    """Async OpenAI call manager with concurrency control and retry.

    Args:
        max_concurrent: Maximum simultaneous API calls (semaphore limit).
        max_retries: Number of retries on RateLimitError (exponential backoff).
    """

    def __init__(self, max_concurrent: int = 10, max_retries: int = 2) -> None:
        self._sem = asyncio.Semaphore(max_concurrent)
        self._max_retries = max_retries
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-initialize the AsyncOpenAI client (reads OPENAI_API_KEY from env)."""
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    async def call(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> str:
        """Make an async chat completion call with semaphore and retry.

        Acquires the semaphore before making the API call. Retries with
        exponential backoff on RateLimitError.

        Args:
            model: OpenAI model name (e.g., "gpt-4.1-mini").
            messages: Chat messages list.
            temperature: Sampling temperature.
            response_format: Optional response format (e.g., {"type": "json_object"}).

        Returns:
            The response content string from choices[0].message.content.

        Raises:
            RateLimitError: If all retries exhausted.
            Exception: Any other API error on the final attempt.
        """
        async with self._sem:
            last_exc: Exception | None = None
            for attempt in range(1 + self._max_retries):
                try:
                    kwargs: dict = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if response_format is not None:
                        kwargs["response_format"] = response_format

                    response = await self.client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content
                except RateLimitError as exc:
                    last_exc = exc
                    wait = 2 ** attempt
                    logger.warning(
                        "Rate limit hit, waiting %ds (attempt %d/%d)",
                        wait, attempt + 1, 1 + self._max_retries,
                    )
                    await asyncio.sleep(wait)

            # All retries exhausted
            raise last_exc  # type: ignore[misc]

    async def stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> AsyncIterator:
        """Make a streaming chat completion call.

        No semaphore -- streaming is typically one synthesis call at a time.
        Returns the async streaming response for token-by-token consumption.

        Args:
            model: OpenAI model name (e.g., "gpt-5.1").
            messages: Chat messages list.
            temperature: Sampling temperature (slightly creative for synthesis).
            max_tokens: Maximum output tokens.

        Returns:
            AsyncIterator of streaming completion chunks.
        """
        # gpt-5.1+ requires max_completion_tokens; older models use max_tokens
        token_param = (
            "max_completion_tokens"
            if model.startswith("gpt-5") or model.startswith("o")
            else "max_tokens"
        )
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            **{token_param: max_tokens},
            stream=True,
            stream_options={"include_usage": True},
        )
        return response
