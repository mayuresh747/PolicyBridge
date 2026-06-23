"""FastAPI server with SSE chat endpoint, document serving, and UI (D-12, D-13, D-14).

Endpoints:
    GET  /                                -- serve chat interface HTML
    POST /api/chat                        -- SSE streaming chat (query -> pipeline -> event stream)
    GET  /api/documents/{library}/{filename} -- serve PDF documents
    GET  /api/relationships/{chunk_id}    -- Kuzu graph relationships for a chunk
    GET  /api/health                      -- health check
    GET  /static/*                        -- static assets (CSS, JS)
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # Load OPENAI_API_KEY before anything else

CHAT_SECRET = os.getenv("CHAT_SECRET", "")
AUDIT_SECRET = os.getenv("AUDIT_SECRET", "")

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from src.config import AGENCY_FOLDERS, DATA_DIR, DOCUMENTS_ROOT, KUZU_PATH, LANCEDB_PATH, LANCEDB_TABLE_NAME
from src.storage.db import lifespan
from src.server.auth import router as auth_router, get_current_user, EXEMPT_PREFIXES
from src.server.conversations import router as conversations_router
from src.storage.trace_collector import TraceCollector
from src.storage.trace_store import TraceStore

import lancedb

from src.graph.kuzu_writer import KuzuWriter
from src.query.pipeline import run_pipeline
from src.retrieval.graph_traversal import get_graph_context

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Seattle Regulatory RAG", version="0.1.0", lifespan=lifespan)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount auth router
app.include_router(auth_router)
# Mount conversations router
app.include_router(conversations_router)


# Two-layer auth middleware: CHAT_SECRET (outer) + JWT (inner) per D-08
@app.middleware("http")
async def check_access(request, call_next):
    # Skip preflight CORS requests (browser sends OPTIONS without custom headers)
    if request.method == "OPTIONS":
        return await call_next(request)

    # --- Layer 1: CHAT_SECRET team gate (unchanged per D-08) ---
    _gated = (request.url.path.startswith("/api/") or request.url.path == "/graph") and \
             request.url.path not in ("/api/health", "/api/audit-check")
    if _gated:
        if CHAT_SECRET:
            key = request.headers.get("X-Access-Key", "") or request.headers.get("x-access-key", "") \
                  or request.query_params.get("key", "")
            if key != CHAT_SECRET:
                return JSONResponse(status_code=403, content={"detail": "Invalid access key"})

    # --- Layer 2: JWT user identity (per D-09) ---
    # Check if path is exempt from JWT
    is_jwt_exempt = not request.url.path.startswith("/api/")
    if not is_jwt_exempt:
        for prefix in EXEMPT_PREFIXES:
            if request.url.path.startswith(prefix):
                is_jwt_exempt = True
                break

    if not is_jwt_exempt:
        # Extract and validate JWT, set request.state.user
        try:
            user = await get_current_user(request)
            request.state.user = user
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    else:
        request.state.user = None

    return await call_next(request)


class ChatRequest(BaseModel):
    """Request body for the /api/chat endpoint (D-13, D-18).

    Attributes:
        query: The user's question.
        agency_filter: Optional list of agency codes to scope retrieval.
        session_id: Optional existing session ID for multi-turn.
        conversation_id: Optional conversation ID for persistence (D-18).
        audit_mode: If True, enable audit event streaming (requires audit_key).
        audit_key: Secret key for enabling audit mode.
    """

    query: str
    agency_filter: list[str] | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    audit_mode: bool = False
    audit_key: str | None = None


@app.post("/api/chat", response_class=EventSourceResponse)
async def chat_endpoint(body: ChatRequest, request: Request):
    """SSE streaming chat endpoint with trace capture and message persistence.

    FastAPI 0.135+ with response_class=EventSourceResponse expects the
    endpoint to be an async generator yielding ServerSentEvent objects.

    Event sequence per D-14:
    status -> sources -> premise_flag (optional) -> token -> usage -> session_id -> done -> conversation

    Save order (D-14, RESEARCH Pattern 3):
    (a) Resolve or create conversation_id
    (b) Save user message to DB
    (c) Create TraceCollector
    (d) Run pipeline, stream SSE, accumulate full_answer
    (e) Save assistant message to DB with trace_id
    (f) Save trace linked to msg_id via TraceStore
    (g) Yield conversation SSE event
    """
    db = request.app.state.db
    user = getattr(request.state, "user", None)

    # Determine effective audit mode
    effective_audit = False
    if body.audit_mode and AUDIT_SECRET and body.audit_key == AUDIT_SECRET:
        effective_audit = True

    # --- (a) Resolve or create conversation_id ---
    conv_id = body.conversation_id
    if user and not conv_id:
        # Auto-create a new conversation; title from first ~80 chars of query
        conv_id = uuid.uuid4().hex
        title = body.query[:80].strip() or "New conversation"
        try:
            await db.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conv_id, user["user_id"], title),
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to create conversation")
            conv_id = None

    # --- (b) Save user message to DB ---
    user_msg_id = None
    if user and conv_id:
        user_msg_id = uuid.uuid4().hex
        try:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, 'user', ?)",
                (user_msg_id, conv_id, body.query),
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to save user message")

    # --- (c) Create TraceCollector (always, per D-14) ---
    collector = TraceCollector()

    # --- (d) Run pipeline, stream SSE, accumulate ---
    full_answer = ""
    sources_json = None

    async for event in run_pipeline(
        query=body.query,
        agency_filter=body.agency_filter,
        session_id=body.session_id,
        audit_mode=effective_audit,
        trace_collector=collector,
    ):
        event_type = event.get("type", "message")
        if event_type == "result":
            continue  # AnswerResult dataclass -- not JSON-serializable, not consumed by client
        event_data = event.get("data", "")

        # Accumulate full answer text from tokens
        if event_type == "token":
            if isinstance(event_data, str):
                full_answer += event_data

        # Capture sources JSON for message persistence
        if event_type == "sources":
            if isinstance(event_data, str):
                sources_json = event_data
            else:
                sources_json = json.dumps(event_data)

        # Serialize non-string data to JSON
        if not isinstance(event_data, str):
            event_data = json.dumps(event_data)
        # Token events: JSON-encode the string so that embedded "\n" becomes
        # "\\n" in the wire payload, preserving SSE framing.  All other events
        # are plain-text or already-serialized JSON -- send raw.
        if event_type == "token":
            event_data = json.dumps(event_data)
        # Use raw_data to prevent FastAPI from double-serializing strings.
        # ServerSentEvent(data=...) calls json.dumps() internally, which
        # would wrap already-serialized JSON strings in extra quotes.
        yield ServerSentEvent(
            raw_data=event_data,
            event=event_type,
        )

    # --- (e) Save assistant message to DB ---
    assistant_msg_id = None
    if user and conv_id and full_answer:
        assistant_msg_id = uuid.uuid4().hex
        try:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, sources_json, trace_id) "
                "VALUES (?, ?, 'assistant', ?, ?, ?)",
                (assistant_msg_id, conv_id, full_answer, sources_json, collector.trace_id),
            )
            # Update conversation updated_at
            await db.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conv_id,),
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to save assistant message")

    # --- (f) Save trace linked to msg_id via TraceStore ---
    if user and assistant_msg_id:
        try:
            trace_store = TraceStore(db)
            await trace_store.save(collector, message_id=assistant_msg_id)
        except Exception:
            logger.exception("Failed to save trace")

    # --- (g) Yield conversation SSE event ---
    if conv_id:
        yield ServerSentEvent(
            raw_data=json.dumps({
                "conversation_id": conv_id,
                "message_id": assistant_msg_id,
            }),
            event="conversation",
        )


@app.get("/api/documents/{library}/{filename}")
async def serve_document(library: str, filename: str):
    """Serve PDF documents from the documents directory.

    Args:
        library: Agency folder key (e.g., "WAC", "RCW", "SMC").
        filename: PDF filename within that folder.
    """
    folder_name = AGENCY_FOLDERS.get(library)
    if not folder_name:
        raise HTTPException(status_code=404, detail=f"Unknown library: {library}")

    file_path = DOCUMENTS_ROOT / folder_name / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")

    return FileResponse(path=str(file_path), media_type="application/pdf")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/audit-check")
async def audit_check():
    """Check if audit mode is available (AUDIT_SECRET configured)."""
    return {"enabled": bool(AUDIT_SECRET)}


@app.post("/api/validate-key")
async def validate_key():
    """Validate the chat access key.

    This endpoint goes through the auth middleware. If the request reaches
    here, the X-Access-Key header was valid (or CHAT_SECRET is empty).
    """
    return {"valid": True}


@app.post("/api/validate-audit-key")
async def validate_audit_key(body: dict):
    """Validate the audit key without exposing the secret.

    Returns {"valid": true} if the provided key matches AUDIT_SECRET.
    """
    if not AUDIT_SECRET:
        return {"valid": False}
    if body.get("audit_key") == AUDIT_SECRET:
        return {"valid": True}
    return JSONResponse(status_code=403, content={"valid": False})


@app.get("/api/relationships/{chunk_id}")
async def get_relationships(chunk_id: str):
    """Return Kuzu graph relationships for a chunk, grouped by type.

    Per D-04: auto-populates relationship panel for the top source.
    Returns max 5 items per relationship type.
    """
    try:
        writer = KuzuWriter(KUZU_PATH)
        try:
            context = get_graph_context(writer, chunk_id)
        finally:
            writer.close()
    except Exception:
        # If Kuzu DB doesn't exist or can't open, return empty
        return {"cites": [], "cited_by": [], "implements": [], "subject_to": []}

    if not context:
        return {"cites": [], "cited_by": [], "implements": [], "subject_to": []}

    grouped = {"cites": [], "cited_by": [], "implements": [], "subject_to": []}
    for edge in context:
        rel = edge["rel_type"].upper()
        direction = edge["direction"]
        entry = {"chunk_id": edge["chunk_id"], "citation": edge["citation"]}

        if rel == "CITES" and direction == "outgoing":
            grouped["cites"].append(entry)
        elif rel == "CITES" and direction == "incoming":
            grouped["cited_by"].append(entry)
        elif rel == "IMPLEMENTS" and direction == "outgoing":
            grouped["implements"].append(entry)
        elif rel == "SUBJECT_TO" and direction == "outgoing":
            grouped["subject_to"].append(entry)
        elif rel == "IMPLEMENTS" and direction == "incoming":
            grouped["cited_by"].append(entry)
        elif rel == "SUBJECT_TO" and direction == "incoming":
            grouped["cited_by"].append(entry)
        elif rel == "DEFINED_BY":
            if direction == "outgoing":
                grouped["subject_to"].append(entry)
            else:
                grouped["cited_by"].append(entry)

    # Cap at 5 per type per D-04
    for key in grouped:
        grouped[key] = grouped[key][:5]

    return grouped


@app.get("/api/chunk/{chunk_id}")
async def get_chunk_text(chunk_id: str):
    """Return full chunk text from LanceDB.

    Used by graph visualization for on-demand text loading.
    """
    if "'" in chunk_id:
        raise HTTPException(status_code=400, detail="Invalid chunk ID")

    try:
        db = lancedb.connect(str(LANCEDB_PATH))
        table = db.open_table(LANCEDB_TABLE_NAME)
        results = table.search().where(f"id = '{chunk_id}'", prefilter=True).limit(1).to_pandas()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to query LanceDB")

    if results.empty:
        raise HTTPException(status_code=404, detail=f"Chunk not found: {chunk_id}")

    row = results.iloc[0]
    return {
        "id": chunk_id,
        "text": str(row.get("text") or ""),
    }


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main chat interface."""
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(), status_code=200)


@app.get("/audit")
async def redirect_audit():
    """Redirect old /audit URL to main page with audit flag."""
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/?audit=true")


@app.get("/graph", response_class=HTMLResponse)
async def serve_graph():
    """Serve the pre-built Kuzu graph visualization."""
    graph_path = DATA_DIR / "graph_visualization.html"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph visualization not built yet. Run scripts/visualize_graph.py first.")
    return HTMLResponse(content=graph_path.read_text(), status_code=200)


# ---- Graph visualization expansion API ----
# Color maps kept in sync with scripts/visualize_graph.py
_VIZ_AGENCY_COLORS: dict[str, str] = {
    "WAC":               "#4A90D9",
    "RCW":               "#27AE60",
    "SMC":               "#E67E22",
    "Seattle DIR":       "#E74C3C",
    "IBC-WA":            "#9B59B6",
    "SPU":               "#1ABC9C",
    "WA Court Opinions": "#F39C12",
    "Governor Orders":   "#EC407A",
}
_VIZ_EDGE_COLORS: dict[str, str] = {
    "CITES":          "#AAAAAA",
    "IMPLEMENTS":     "#4A90D9",
    "NEXT_SECTION":   "#444444",
    "SUBJECT_TO":     "#9B59B6",
    "DEFINED_BY":     "#1ABC9C",
    "AMENDED_BY":     "#E74C3C",
    "CONFLICTS_WITH": "#FF3333",
    "DOC_HAS_CHUNK":  "#B8860B",
}
_DEFAULT_NODE_COLOR = "#95A5A6"
_CROSS_CHUNK_RELS = ["CITES", "IMPLEMENTS", "DEFINED_BY", "SUBJECT_TO", "AMENDED_BY", "NEXT_SECTION"]


def _fmt_viz_edge(src: str, tgt: str, rel: str, conf: float) -> dict:
    """Format an edge dict for graph expand/edges API responses."""
    return {
        "from": src,
        "to": tgt,
        "rel": rel,
        "color": _VIZ_EDGE_COLORS.get(rel, "#888"),
        "title": f"{rel} (conf: {conf:.2f})",
        "width": 1 if rel in ("NEXT_SECTION", "DOC_HAS_CHUNK") else 2,
        "dashes": rel == "NEXT_SECTION",
    }


@app.get("/api/graph/expand/{doc_id}")
async def expand_document_graph(doc_id: str, loaded_docs: str = ""):
    """Return chunk nodes + edges for on-demand graph expansion.

    Called by the visualization when the user clicks a document node.

    Args:
        doc_id: The DocumentNode id to expand.
        loaded_docs: Comma-separated document IDs already loaded in the browser.
            Edges whose target chunk belongs to a loaded doc are returned as
            graph edges; others are returned as pending_connections.

    Returns:
        nodes: Chunk nodes for this document (with metadata for detail panel).
        edges: DOC_HAS_CHUNK edges + cross-chunk edges where both endpoints
            are in loaded documents.
        pending_connections: List of {target_doc_id, target_doc_label, rel_type,
            count} for cross-chunk edges to unloaded documents.
    """
    loaded_set: set[str] = set(filter(None, loaded_docs.split(",")))
    loaded_set.add(doc_id)

    try:
        writer = KuzuWriter(KUZU_PATH)
        try:
            # 1. Get this doc's chunks with metadata
            chunk_rows = writer.query(
                "MATCH (d:DocumentNode)-[:DOC_HAS_CHUNK]->(c:Chunk) "
                "WHERE d.id = $doc_id "
                "RETURN c.id, c.agency, c.citation, c.authority_level, "
                "       c.chunk_index, c.filename "
                "ORDER BY c.chunk_index",
                params={"doc_id": doc_id},
            )
            chunk_ids = [r[0] for r in chunk_rows]
            chunk_meta_map = {
                r[0]: {
                    "agency": r[1] or "",
                    "citation": r[2] or "",
                    "authority_level": r[3] or "",
                    "chunk_index": int(r[4] or 0),
                    "filename": r[5] or "",
                }
                for r in chunk_rows
            }

            # 2. Query outgoing cross-chunk edges from this doc's chunks
            all_edges: list[dict] = []
            seen_edges: set[tuple] = set()

            for rel in _CROSS_CHUNK_RELS:
                rows = writer.query(
                    f"MATCH (d:DocumentNode)-[:DOC_HAS_CHUNK]->(src:Chunk)"
                    f"-[r:{rel}]->(tgt:Chunk)<-[:DOC_HAS_CHUNK]-(td:DocumentNode) "
                    f"WHERE d.id = $doc_id "
                    f"RETURN src.id, tgt.id, r.confidence, td.id, td.label",
                    params={"doc_id": doc_id},
                )
                for src_id, tgt_id, conf, tgt_doc_id, tgt_doc_label in rows:
                    key = (src_id, tgt_id, rel)
                    if key not in seen_edges:
                        seen_edges.add(key)
                        all_edges.append({
                            "from": src_id,
                            "to": tgt_id,
                            "rel": rel,
                            "confidence": float(conf or 1.0),
                            "target_doc_id": tgt_doc_id,
                            "target_doc_label": tgt_doc_label or tgt_doc_id,
                        })
        finally:
            writer.close()
    except Exception:
        logger.exception("expand_document_graph error for %s", doc_id)
        raise HTTPException(status_code=500, detail=f"Failed to expand {doc_id}")

    # 3. DOC_HAS_CHUNK edges (always included — both endpoints known)
    doc_has_chunk_edges = [
        _fmt_viz_edge(doc_id, cid, "DOC_HAS_CHUNK", 1.0) for cid in chunk_ids
    ]

    # 4. Split cross-chunk edges: graph (target loaded) vs pending
    graph_edges: list[dict] = []
    pending_map: dict[tuple, dict] = {}

    for e in all_edges:
        tgt_doc_id = e["target_doc_id"]
        if tgt_doc_id in loaded_set:
            graph_edges.append(_fmt_viz_edge(e["from"], e["to"], e["rel"], e["confidence"]))
        else:
            key = (tgt_doc_id, e["rel"])
            if key not in pending_map:
                pending_map[key] = {
                    "target_doc_id": tgt_doc_id,
                    "target_doc_label": e["target_doc_label"],
                    "rel_type": e["rel"],
                    "count": 0,
                }
            pending_map[key]["count"] += 1

    # 5. Build node list
    nodes = [
        {
            "id": cid,
            "label": meta["citation"] or f"chunk-{meta['chunk_index']}",
            "color": _VIZ_AGENCY_COLORS.get(meta["agency"], _DEFAULT_NODE_COLOR),
            "agency": meta["agency"],
            "authority_level": meta["authority_level"],
            "chunk_index": meta["chunk_index"],
            "filename": meta["filename"],
        }
        for cid, meta in chunk_meta_map.items()
    ]

    return {
        "nodes": nodes,
        "edges": doc_has_chunk_edges + graph_edges,
        "pending_connections": list(pending_map.values()),
    }


@app.get("/api/graph/edges")
async def get_cross_doc_edges(doc_a: str, doc_b: str):
    """Return cross-chunk edges between two documents' chunks (both directions).

    Called by the visualization after a second document is loaded, to auto-wire
    edges that cross between the two newly co-loaded documents.

    Args:
        doc_a: First DocumentNode id.
        doc_b: Second DocumentNode id.

    Returns:
        edges: All cross-chunk edges between doc_a and doc_b chunks, both
            A→B and B→A directions, for all cross-chunk relationship types.
    """
    try:
        writer = KuzuWriter(KUZU_PATH)
        try:
            edges: list[dict] = []
            seen: set[tuple] = set()

            for rel in _CROSS_CHUNK_RELS:
                # A → B
                rows = writer.query(
                    f"MATCH (da:DocumentNode)-[:DOC_HAS_CHUNK]->(src:Chunk)"
                    f"-[r:{rel}]->(tgt:Chunk)<-[:DOC_HAS_CHUNK]-(db:DocumentNode) "
                    f"WHERE da.id = $doc_a AND db.id = $doc_b "
                    f"RETURN src.id, tgt.id, r.confidence",
                    params={"doc_a": doc_a, "doc_b": doc_b},
                )
                for src_id, tgt_id, conf in rows:
                    key = (src_id, tgt_id, rel)
                    if key not in seen:
                        seen.add(key)
                        edges.append(_fmt_viz_edge(src_id, tgt_id, rel, float(conf or 1.0)))

                # B → A
                rows = writer.query(
                    f"MATCH (db:DocumentNode)-[:DOC_HAS_CHUNK]->(src:Chunk)"
                    f"-[r:{rel}]->(tgt:Chunk)<-[:DOC_HAS_CHUNK]-(da:DocumentNode) "
                    f"WHERE db.id = $doc_b AND da.id = $doc_a "
                    f"RETURN src.id, tgt.id, r.confidence",
                    params={"doc_b": doc_b, "doc_a": doc_a},
                )
                for src_id, tgt_id, conf in rows:
                    key = (src_id, tgt_id, rel)
                    if key not in seen:
                        seen.add(key)
                        edges.append(_fmt_viz_edge(src_id, tgt_id, rel, float(conf or 1.0)))
        finally:
            writer.close()
    except Exception:
        logger.exception("get_cross_doc_edges error for %s / %s", doc_a, doc_b)
        raise HTTPException(status_code=500, detail="Failed to query cross-doc edges")

    return {"edges": edges}


# Static file mount -- MUST be last (catches all unmatched paths under /static/)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
