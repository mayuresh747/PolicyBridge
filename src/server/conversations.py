"""Conversation management API endpoints (PERS-05).

Provides CRUD operations for conversations and a trace retrieval
endpoint. All endpoints require JWT authentication and enforce
ownership checks (D-20).

Endpoints:
    GET    /api/conversations                  -- List user's conversations
    GET    /api/conversations/{conversation_id} -- Get conversation with messages
    DELETE /api/conversations/{conversation_id} -- Delete conversation
    PATCH  /api/conversations/{conversation_id} -- Update conversation title
    GET    /api/messages/{message_id}/trace     -- Get trace for a message
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.storage.conversation_store import ConversationStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["conversations"])


class TitleUpdate(BaseModel):
    """Request body for PATCH /api/conversations/{id}."""
    title: str


def _get_store(request: Request) -> ConversationStore:
    """Get ConversationStore from the app's shared DB connection."""
    return ConversationStore(request.app.state.db)


def _get_user_id(request: Request) -> str:
    """Extract user_id from request.state.user set by auth middleware.

    Raises 401 if no user is attached (auth middleware should have caught this,
    but defensive check for direct calls).
    """
    user = getattr(request.state, "user", None)
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return user["user_id"]


@router.get("/conversations")
async def list_conversations(request: Request):
    """List the authenticated user's conversations, newest first."""
    user_id = _get_user_id(request)
    store = _get_store(request)
    conversations = await store.list_conversations(user_id)
    return conversations


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    """Get a conversation with its messages. 403 if not owner."""
    user_id = _get_user_id(request)
    store = _get_store(request)

    if not await store.verify_ownership(conversation_id, user_id):
        raise HTTPException(status_code=403, detail="Not your conversation")

    messages = await store.load_messages(conversation_id)

    # Get conversation title
    convos = await store.list_conversations(user_id)
    title = next((c["title"] for c in convos if c["id"] == conversation_id), "")

    return {
        "id": conversation_id,
        "title": title,
        "messages": messages,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    """Delete a conversation and its messages. 403 if not owner."""
    user_id = _get_user_id(request)
    store = _get_store(request)

    if not await store.verify_ownership(conversation_id, user_id):
        raise HTTPException(status_code=403, detail="Not your conversation")

    await store.delete_conversation(conversation_id)
    return {"ok": True}


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str, body: TitleUpdate, request: Request
):
    """Update a conversation's title. 403 if not owner."""
    user_id = _get_user_id(request)
    store = _get_store(request)

    if not await store.verify_ownership(conversation_id, user_id):
        raise HTTPException(status_code=403, detail="Not your conversation")

    await store.update_title(conversation_id, body.title)
    return {"ok": True}


@router.get("/messages/{message_id}/trace")
async def get_message_trace(message_id: str, request: Request):
    """Get trace data for a message.

    Uses raw SQL against the traces table. Does NOT import TraceStore
    (created in parallel Plan 07-04 and may not exist yet).
    """
    db = request.app.state.db
    cursor = await db.execute(
        "SELECT id, stages_json, file_path, total_ms "
        "FROM traces WHERE message_id = ?",
        (message_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No trace found for this message")

    trace_id = row["id"]
    total_ms = row["total_ms"]
    stages = None

    # Try file_path first, then inline stages_json
    file_path = row["file_path"]
    if file_path and Path(file_path).exists():
        try:
            stages = json.loads(Path(file_path).read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read trace file %s: %s", file_path, exc)

    if stages is None and row["stages_json"]:
        try:
            stages = json.loads(row["stages_json"])
        except json.JSONDecodeError:
            stages = []

    if stages is None:
        stages = []

    return {"trace_id": trace_id, "stages": stages, "total_ms": total_ms}
