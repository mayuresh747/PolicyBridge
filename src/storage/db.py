"""SQLite database connection manager with WAL mode and schema DDL.

Provides a single aiosqlite connection via FastAPI lifespan. All tables
are created on first run (CREATE IF NOT EXISTS). Schema versioning is
tracked via the schema_version table for future migrations.
"""

import aiosqlite
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from src.config import DB_PATH, TRACE_DIR, TRACE_RETENTION_DAYS, MAX_CONVERSATIONS_PER_USER

logger = logging.getLogger(__name__)


async def init_db(db_path: str = None) -> aiosqlite.Connection:
    """Open an aiosqlite connection with WAL mode and create all tables.

    Args:
        db_path: Optional path override (used by tests with tmp_path).
                 Defaults to DB_PATH from config.

    Returns:
        An open aiosqlite.Connection with row_factory set to aiosqlite.Row.
    """
    path = db_path or str(DB_PATH)
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row

    # Set PRAGMAs for WAL mode, busy timeout, autocheckpoint, and foreign keys
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA wal_autocheckpoint=1000")
    await db.execute("PRAGMA foreign_keys=ON")

    await _create_tables(db)
    return db


async def _create_tables(db: aiosqlite.Connection):
    """Create tables if they don't exist. Schema v1."""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_conv_user
            ON conversations(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            sources_json TEXT,
            trace_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_msg_conv
            ON messages(conversation_id, created_at);

        CREATE TABLE IF NOT EXISTS traces (
            id TEXT PRIMARY KEY,
            message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
            stages_json TEXT,
            file_path TEXT,
            total_ms REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    await db.commit()


async def run_cleanup(db: aiosqlite.Connection) -> dict:
    """Run all startup cleanup tasks per D-27. Returns counts of deleted items.

    Three operations:
    1. Delete traces older than TRACE_RETENTION_DAYS (and their disk files).
    2. Delete orphan conversations (conversations with 0 messages).
    3. Enforce per-user conversation cap (MAX_CONVERSATIONS_PER_USER).

    Args:
        db: An open aiosqlite.Connection with row_factory set.

    Returns:
        dict with keys: traces_deleted, orphans_deleted, cap_deleted.
    """
    results = {}

    # 1. Delete traces older than TRACE_RETENTION_DAYS
    cutoff_sql = f"datetime('now', '-{TRACE_RETENTION_DAYS} days')"

    # First, find and delete disk trace files for expired traces
    cursor = await db.execute(
        f"SELECT file_path FROM traces WHERE file_path IS NOT NULL AND created_at < {cutoff_sql}"
    )
    for row in await cursor.fetchall():
        try:
            Path(row["file_path"]).unlink(missing_ok=True)
        except OSError:
            pass

    cursor = await db.execute(
        f"DELETE FROM traces WHERE created_at < {cutoff_sql}"
    )
    results["traces_deleted"] = cursor.rowcount

    # 2. Delete orphan conversations (0 messages)
    cursor = await db.execute("""
        DELETE FROM conversations WHERE id NOT IN (
            SELECT DISTINCT conversation_id FROM messages
        )
    """)
    results["orphans_deleted"] = cursor.rowcount

    # 3. Enforce per-user conversation cap
    # Find all users who exceed the cap
    cursor = await db.execute("""
        SELECT user_id, COUNT(*) as cnt FROM conversations
        GROUP BY user_id HAVING cnt > ?
    """, (MAX_CONVERSATIONS_PER_USER,))
    over_cap_users = await cursor.fetchall()

    cap_deleted = 0
    for row in over_cap_users:
        user_id = row["user_id"]
        excess = row["cnt"] - MAX_CONVERSATIONS_PER_USER
        # Delete the oldest excess conversations (by updated_at ASC)
        cursor = await db.execute("""
            DELETE FROM conversations WHERE id IN (
                SELECT id FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at ASC
                LIMIT ?
            )
        """, (user_id, excess))
        cap_deleted += cursor.rowcount
    results["cap_deleted"] = cap_deleted

    await db.commit()
    return results


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan: open DB on startup, close on shutdown.

    Creates the data/traces/ directory if it doesn't exist (D-16).
    Stores the connection on app.state.db for request handlers.
    Runs startup cleanup per D-27.
    """
    # Ensure traces directory exists
    Path(TRACE_DIR).mkdir(parents=True, exist_ok=True)

    app.state.db = await init_db()
    # Run startup cleanup per D-27
    cleanup_results = await run_cleanup(app.state.db)
    logger.info(f"Startup cleanup: {cleanup_results}")
    try:
        yield
    finally:
        await app.state.db.close()


async def close_db(db: aiosqlite.Connection):
    """Close the database connection."""
    await db.close()
