"""Multi-turn session manager and follow-up query rewriter (Plan 04-05).

Implements D-16, D-17, D-18, D-19:
- In-memory session store keyed by session_id (D-16)
- Last 5 turns + chunk cache + agency filter per session (D-17)
- GPT-4.1-mini follow-up rewriting into standalone queries (D-18)
- 60-minute inactivity TTL with cleanup (D-19)

Public API:
    SessionState -- per-session dataclass
    SessionManager -- session CRUD with TTL enforcement
    rewrite_follow_up() -- rewrite vague follow-ups into standalone queries
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.config import MAX_SESSION_TURNS, QUERY_LLM_MODEL, SESSION_TTL_MINUTES
from src.retrieval.models import RetrievalResult

if TYPE_CHECKING:
    from src.query.llm import LLMCallManager
    from src.storage.conversation_store import ConversationStore


@dataclass
class SessionState:
    """Per-session state for multi-turn conversations (D-17).

    Attributes:
        turns: Conversation history as {role, content} dicts. Capped at
            max_turns * 2 messages (each turn = 1 user + 1 assistant).
        chunk_cache: Previously retrieved chunks keyed by chunk_id.
            Capped at max_cache_size. Provides RRF boost for follow-ups.
        agency_filter: Active agency scope, persists across turns.
        referenced_sections: Fast lookup mapping citation -> chunk_id
            for resolving "that section" style follow-ups.
        created_at: Session creation timestamp.
        last_active: Last activity timestamp (updated on each access).
    """

    turns: list[dict] = field(default_factory=list)
    chunk_cache: dict[str, RetrievalResult] = field(default_factory=dict)
    agency_filter: list[str] | None = None
    referenced_sections: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionManager:
    """In-memory session manager with TTL enforcement (D-16, D-19).

    Sessions are stored in a Python dict. Lost on server restart.
    Interface designed for later swap to SQLite/Redis without downstream
    changes.

    When a ConversationStore is injected, cold-loading a conversation
    populates turns from the database (D-10). chunk_cache, agency_filter,
    and referenced_sections stay empty on cold load (D-11, D-12).

    Args:
        ttl_minutes: Inactivity timeout in minutes (default: SESSION_TTL_MINUTES).
        max_turns: Maximum conversation turns to keep (default: MAX_SESSION_TURNS).
        max_cache_size: Maximum cached chunks per session (default: 100).
        conversation_store: Optional ConversationStore for DB-backed turn loading.
    """

    def __init__(
        self,
        ttl_minutes: int = SESSION_TTL_MINUTES,
        max_turns: int = MAX_SESSION_TURNS,
        max_cache_size: int = 100,
        conversation_store: ConversationStore | None = None,
    ) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_turns = max_turns
        self._max_cache_size = max_cache_size
        self._store = conversation_store

    async def get_or_create(self, session_id: str | None) -> tuple[str, SessionState]:
        """Get existing session or create new one.

        Cleans expired sessions first. If session_id is provided but
        expired or unknown, creates a new session with a fresh ID.

        When a ConversationStore is injected and the session_id refers
        to a conversation not yet in memory, loads turns from DB (D-10).

        Args:
            session_id: Existing session/conversation ID, or None for new session.

        Returns:
            Tuple of (session_id, SessionState).
        """
        self._cleanup_expired()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_active = datetime.now(timezone.utc)
            return session_id, session

        # If we have a store and a conversation_id, try cold-loading from DB
        if session_id and self._store:
            messages = await self._store.load_messages(session_id)
            if messages:
                state = SessionState()
                state.turns = [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                ]
                self._sessions[session_id] = state
                return session_id, state

        new_id = session_id or secrets.token_urlsafe(16)
        self._sessions[new_id] = SessionState()
        return new_id, self._sessions[new_id]

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Add a user+assistant turn pair to the session.

        Keeps only the last max_turns turns (each turn = 2 messages).

        Args:
            session_id: Session to update.
            user_msg: User's query text.
            assistant_msg: Assistant's response text.
        """
        session = self._sessions[session_id]
        session.turns.append({"role": "user", "content": user_msg})
        session.turns.append({"role": "assistant", "content": assistant_msg})

        # Keep last max_turns * 2 messages (each turn = 2 messages)
        max_messages = self._max_turns * 2
        if len(session.turns) > max_messages:
            session.turns = session.turns[-max_messages:]

    def add_to_chunk_cache(
        self, session_id: str, results: list[RetrievalResult]
    ) -> None:
        """Cache retrieval results for follow-up queries.

        Stores by chunk_id. Also populates referenced_sections for
        citation-based follow-up resolution. Evicts oldest entries
        when over max_cache_size.

        Args:
            session_id: Session to update.
            results: RetrievalResult objects to cache.
        """
        session = self._sessions[session_id]
        for r in results:
            session.chunk_cache[r.chunk_id] = r
            session.referenced_sections[r.citation] = r.chunk_id

        # Evict oldest if over cap (dict is insertion-ordered in Python 3.7+)
        while len(session.chunk_cache) > self._max_cache_size:
            oldest_key = next(iter(session.chunk_cache))
            del session.chunk_cache[oldest_key]

    def _cleanup_expired(self) -> None:
        """Remove sessions that have been inactive longer than TTL."""
        now = datetime.now(timezone.utc)
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]


# ---------------------------------------------------------------------------
# Follow-up query rewriter (D-18)
# ---------------------------------------------------------------------------

REWRITE_PROMPT = """You rewrite follow-up questions into standalone queries.

Given the conversation history and a follow-up question, rewrite it as a self-contained question
that includes all necessary context from the conversation.

Conversation history:
{history}

Follow-up question: {query}

Rewrite as a standalone question (return ONLY the rewritten question, nothing else):"""


async def rewrite_follow_up(
    query: str, turns: list[dict], llm: LLMCallManager
) -> str:
    """Rewrite a vague follow-up into a standalone query using conversation history.

    Uses GPT-4.1-mini to incorporate context from recent turns into the
    follow-up question, making it self-contained for the retrieval pipeline.

    If turns is empty (first message in session), returns query unchanged.

    Args:
        query: The user's follow-up query.
        turns: Conversation history ({role, content} dicts).
        llm: LLMCallManager for making the rewrite call.

    Returns:
        Rewritten standalone query, or original query if no history.
    """
    if not turns:
        return query

    # Use last 2 turns (4 messages) for context
    history = "\n".join(
        f"{t['role'].title()}: {t['content'][:200]}" for t in turns[-4:]
    )

    result = await llm.call(
        model=QUERY_LLM_MODEL,
        messages=[
            {"role": "user", "content": REWRITE_PROMPT.format(history=history, query=query)},
        ],
        temperature=0.0,
    )

    return result.strip() if result.strip() else query
