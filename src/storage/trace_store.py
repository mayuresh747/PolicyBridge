"""TraceStore: save/load/cleanup pipeline traces from SQLite and disk (PERS-04).

Traces under 50KB are stored inline in the stages_json column.
Traces over 50KB are offloaded to data/traces/{id}.json with the
file_path stored in SQLite (per D-16).
"""

import json
from pathlib import Path

import aiosqlite

from src.config import TRACE_DIR, TRACE_RETENTION_DAYS
from src.storage.trace_collector import TraceCollector


class TraceStore:
    """Persist and retrieve pipeline traces from SQLite + optional disk offload."""

    INLINE_THRESHOLD = 50 * 1024  # 50KB per D-16

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def save(
        self,
        collector: TraceCollector,
        message_id: str | None = None,
        trace_dir: Path | None = None,
    ) -> str:
        """Save a completed trace. Offloads to disk if >50KB.

        Args:
            collector: The TraceCollector with accumulated stages.
            message_id: Optional FK to messages(id) for the assistant response.
            trace_dir: Override trace directory (used by tests with tmp_path).
                       Defaults to TRACE_DIR from config.

        Returns:
            The trace_id string.
        """
        stages_json_str = json.dumps(collector.stages)
        target_dir = Path(trace_dir) if trace_dir else TRACE_DIR

        if len(stages_json_str.encode("utf-8")) > self.INLINE_THRESHOLD:
            # Write to disk
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(target_dir / f"{collector.trace_id}.json")
            Path(file_path).write_text(stages_json_str)
            await self.db.execute(
                "INSERT INTO traces (id, message_id, file_path, total_ms) VALUES (?,?,?,?)",
                (collector.trace_id, message_id, file_path, collector.total_ms),
            )
        else:
            # Store inline
            await self.db.execute(
                "INSERT INTO traces (id, message_id, stages_json, total_ms) VALUES (?,?,?,?)",
                (collector.trace_id, message_id, stages_json_str, collector.total_ms),
            )
        await self.db.commit()
        return collector.trace_id

    async def get_by_id(self, trace_id: str) -> dict | None:
        """Retrieve a trace by its trace_id.

        Returns:
            Dict with trace_id, stages, total_ms, or None if not found.
        """
        cursor = await self.db.execute(
            "SELECT id, stages_json, file_path, total_ms FROM traces WHERE id = ?",
            (trace_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._load_trace(row)

    async def get_by_message(self, message_id: str) -> dict | None:
        """Retrieve a trace by the associated message_id.

        Returns:
            Dict with trace_id, stages, total_ms, or None if not found.
        """
        cursor = await self.db.execute(
            "SELECT id, stages_json, file_path, total_ms FROM traces WHERE message_id = ?",
            (message_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._load_trace(row)

    def _load_trace(self, row) -> dict:
        """Deserialize a trace row (inline or disk) into a dict."""
        if row["file_path"]:
            stages = json.loads(Path(row["file_path"]).read_text())
        else:
            stages = json.loads(row["stages_json"])
        return {
            "trace_id": row["id"],
            "stages": stages,
            "total_ms": row["total_ms"],
        }

    async def cleanup(self, retention_days: int | None = None) -> int:
        """Delete traces older than retention_days. Remove disk files too.

        Args:
            retention_days: Override for TRACE_RETENTION_DAYS config value.

        Returns:
            Number of traces deleted.
        """
        days = retention_days if retention_days is not None else TRACE_RETENTION_DAYS
        # Find disk traces to delete
        cursor = await self.db.execute(
            "SELECT file_path FROM traces WHERE file_path IS NOT NULL "
            "AND created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        for row in await cursor.fetchall():
            try:
                Path(row["file_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        # Delete from DB
        cursor = await self.db.execute(
            "DELETE FROM traces WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        deleted = cursor.rowcount
        await self.db.commit()
        return deleted
