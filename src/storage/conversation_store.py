"""Async CRUD interface for conversations and messages (PERS-03).

Thin wrapper around SQL queries for the conversations and messages tables.
Accepts the shared aiosqlite connection from FastAPI lifespan.

Pattern 2 from 07-RESEARCH.md.
"""

from __future__ import annotations

import uuid

import aiosqlite


class ConversationStore:
    """Conversation and message persistence backed by SQLite.

    Args:
        db: An open aiosqlite.Connection with row_factory=aiosqlite.Row.
    """

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create_conversation(self, user_id: str, title: str) -> str:
        """Create a new conversation and return its 32-char hex ID."""
        conv_id = uuid.uuid4().hex
        await self.db.execute(
            "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
            (conv_id, user_id, title),
        )
        await self.db.commit()
        return conv_id

    async def list_conversations(self, user_id: str) -> list[dict]:
        """List conversations for a user, ordered by updated_at DESC."""
        cursor = await self.db.execute(
            "SELECT id, title, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def load_messages(self, conversation_id: str) -> list[dict]:
        """Load messages for a conversation, ordered by created_at ASC."""
        cursor = await self.db.execute(
            "SELECT id, role, content, sources_json, trace_id, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources_json: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        """Save a message and update conversation's updated_at. Returns 32-char hex message_id."""
        msg_id = uuid.uuid4().hex
        await self.db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources_json, trace_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, sources_json, trace_id),
        )
        await self.db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await self.db.commit()
        return msg_id

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation. ON DELETE CASCADE removes its messages."""
        await self.db.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        await self.db.commit()

    async def verify_ownership(
        self, conversation_id: str, user_id: str
    ) -> bool:
        """Check if a conversation belongs to the given user."""
        cursor = await self.db.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        return await cursor.fetchone() is not None

    async def update_title(self, conversation_id: str, title: str) -> None:
        """Update a conversation's title."""
        await self.db.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )
        await self.db.commit()
