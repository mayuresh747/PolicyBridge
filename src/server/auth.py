"""User identity: registration, login, JWT generation, and auth dependency.

No passwords per D-05 -- email-only identity lookup behind CHAT_SECRET team gate.
JWT signed with HS256 using JWT_SECRET (auto-generated if not set).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.config import JWT_SECRET, JWT_EXPIRY_DAYS

# Paths exempt from JWT requirement per D-09
# Graph/chunk/relationship endpoints serve the standalone graph viz page which
# has no JWT flow — they remain protected by the CHAT_SECRET team gate (Layer 1).
EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/health",
    "/api/audit-check",
    "/api/validate-key",
    "/api/graph/",
    "/api/graph",
    "/api/chunk/",
    "/api/relationships/",
    "/audit",
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- JWT utility functions ----------


def create_token(user_id: str, email: str) -> str:
    """Create a signed JWT with sub, email, iat, exp claims."""
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt exceptions on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


# ---------- FastAPI dependency ----------


async def get_current_user(request: Request) -> dict | None:
    """Extract user identity from JWT Bearer token.

    Returns user dict {user_id, email} or None for exempt paths.
    Raises HTTPException(401) for missing/invalid/expired tokens on non-exempt paths.
    """
    # Check if path is exempt from JWT per D-09
    for prefix in EXEMPT_PREFIXES:
        if request.url.path.startswith(prefix):
            return None

    # Non-API paths (static files, HTML pages) don't require JWT
    if not request.url.path.startswith("/api/"):
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
        return {"user_id": payload["sub"], "email": payload["email"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------- Request models ----------


class RegisterRequest(BaseModel):
    name: str
    email: str


class LoginRequest(BaseModel):
    email: str


# ---------- Endpoints ----------


@router.post("/register")
async def register(body: RegisterRequest, request: Request):
    """Register a new user with name + email. Returns JWT and user info.

    No password per D-05 -- email-only identity behind CHAT_SECRET team gate.
    """
    db = request.app.state.db
    user_id = uuid.uuid4().hex
    try:
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, body.name, body.email),
        )
        await db.commit()
    except Exception as e:
        # aiosqlite wraps sqlite3.IntegrityError
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=409, detail="Email already registered")
        raise

    token = create_token(user_id, body.email)
    return {
        "token": token,
        "user": {"user_id": user_id, "name": body.name, "email": body.email},
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    """Login with email. Returns JWT and user info. No password per D-05."""
    db = request.app.state.db
    cursor = await db.execute(
        "SELECT id, name, email FROM users WHERE email = ?", (body.email,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_token(row["id"], row["email"])
    return {
        "token": token,
        "user": {"user_id": row["id"], "name": row["name"], "email": row["email"]},
    }


@router.get("/me")
async def me(request: Request):
    """Return current user info from JWT. Requires valid Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = request.app.state.db
    cursor = await db.execute(
        "SELECT id, name, email FROM users WHERE id = ?", (payload["sub"],)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": row["id"], "name": row["name"], "email": row["email"]}
