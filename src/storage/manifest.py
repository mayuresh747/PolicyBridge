"""Ingestion manifest and failure logging for resumable PDF processing.

ManifestEntry: dataclass representing the processing state of a single PDF.
IngestionManifest: JSON-backed manifest that tracks every PDF through the
    ingestion pipeline — supports checkpointing, resume, and change detection.
FailureLog: append-only JSON log of all processing failures with timestamps.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.config import FAILURES_PATH, MANIFEST_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ManifestEntry:
    """Processing state for a single PDF document."""

    status: str  # "complete" | "failed" | "in_progress"
    agency: str
    chunk_count: int = 0
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    file_hash: Optional[str] = None  # sha256 hash for change detection


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class IngestionManifest:
    """JSON-backed manifest for tracking PDF ingestion state.

    Enables resumable ingestion: documents marked ``complete`` are skipped on
    re-runs; ``failed`` documents are skipped unless ``resume_failed=True``;
    ``in_progress`` and untracked documents are always processed.

    The manifest is saved atomically (write to ``.tmp``, then ``os.replace``)
    to prevent corruption from interrupted writes.

    Usage::

        manifest = IngestionManifest()
        manifest.load()
        unprocessed = manifest.get_unprocessed(all_pdf_paths)
        for pdf in unprocessed:
            manifest.mark_in_progress(pdf, agency)
            # ... process ...
            manifest.mark_complete(pdf, chunk_count)
            manifest.save()
    """

    def __init__(self, manifest_path: str | Path | None = None):
        """Initialise the manifest, loading from disk if the file exists.

        Args:
            manifest_path: Path to the manifest JSON file.  Defaults to
                ``config.MANIFEST_PATH``.
        """
        self._path = Path(manifest_path) if manifest_path is not None else MANIFEST_PATH
        self._version: int = 1
        self._last_updated: Optional[str] = None
        self._documents: Dict[str, ManifestEntry] = {}

        if self._path.exists():
            self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load manifest from JSON file on disk."""
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._version = data.get("version", 1)
        self._last_updated = data.get("last_updated")

        self._documents = {}
        for pdf_path, entry_dict in data.get("documents", {}).items():
            self._documents[pdf_path] = ManifestEntry(**entry_dict)

        logger.info(
            "Loaded manifest with %d documents from %s",
            len(self._documents),
            self._path,
        )

    def save(self) -> None:
        """Atomically save manifest to JSON file.

        Writes to a temporary file first, then uses ``os.replace`` to rename
        it to the target path.  This prevents partial writes from corrupting
        the manifest.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._last_updated = datetime.datetime.utcnow().isoformat()

        data = {
            "version": self._version,
            "last_updated": self._last_updated,
            "documents": {
                path: asdict(entry)
                for path, entry in self._documents.items()
            },
        }

        tmp_path = self._path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        os.replace(str(tmp_path), str(self._path))
        logger.debug("Saved manifest (%d documents)", len(self._documents))

    # ------------------------------------------------------------------
    # Status tracking
    # ------------------------------------------------------------------

    def get_status(self, pdf_path: str) -> Optional[str]:
        """Return the status for a PDF path, or ``None`` if not tracked.

        Args:
            pdf_path: Absolute path to the PDF file.
        """
        abs_path = str(Path(pdf_path).resolve())
        entry = self._documents.get(abs_path)
        return entry.status if entry else None

    def mark_in_progress(self, pdf_path: str, agency: str) -> None:
        """Mark a document as ``in_progress`` with a ``started_at`` timestamp.

        Args:
            pdf_path: Absolute path to the PDF file.
            agency: Agency identifier (e.g. ``"WAC"``).
        """
        abs_path = str(Path(pdf_path).resolve())
        self._documents[abs_path] = ManifestEntry(
            status="in_progress",
            agency=agency,
            started_at=datetime.datetime.utcnow().isoformat(),
            file_hash=self.compute_file_hash(pdf_path) if Path(pdf_path).exists() else None,
        )

    def mark_complete(self, pdf_path: str, chunk_count: int) -> None:
        """Mark a document as ``complete`` with chunk count and ``completed_at``.

        Args:
            pdf_path: Absolute path to the PDF file.
            chunk_count: Number of chunks produced from this document.
        """
        abs_path = str(Path(pdf_path).resolve())
        entry = self._documents.get(abs_path)
        if entry is None:
            entry = ManifestEntry(status="complete", agency="unknown")
            self._documents[abs_path] = entry

        entry.status = "complete"
        entry.chunk_count = chunk_count
        entry.completed_at = datetime.datetime.utcnow().isoformat()

    def mark_failed(self, pdf_path: str, error: str, stack_trace: str) -> None:
        """Mark a document as ``failed`` with error details.

        Args:
            pdf_path: Absolute path to the PDF file.
            error: Short error message.
            stack_trace: Full stack trace string.
        """
        abs_path = str(Path(pdf_path).resolve())
        entry = self._documents.get(abs_path)
        if entry is None:
            entry = ManifestEntry(status="failed", agency="unknown")
            self._documents[abs_path] = entry

        entry.status = "failed"
        entry.error = error
        entry.stack_trace = stack_trace
        entry.completed_at = datetime.datetime.utcnow().isoformat()

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def get_unprocessed(
        self, pdf_paths: List[str], resume_failed: bool = False
    ) -> List[str]:
        """Filter *pdf_paths* to return only those needing processing.

        - ``complete`` documents are always skipped.
        - ``failed`` documents are skipped unless *resume_failed* is ``True``.
        - ``in_progress`` and untracked documents are always included.

        Args:
            pdf_paths: List of PDF file paths to check.
            resume_failed: If ``True``, re-attempt previously failed documents.

        Returns:
            Subset of *pdf_paths* that should be processed.
        """
        result: List[str] = []
        for p in pdf_paths:
            abs_path = str(Path(p).resolve())
            entry = self._documents.get(abs_path)
            if entry is None:
                # Untracked — always process
                result.append(p)
            elif entry.status == "complete":
                # Already done — skip
                continue
            elif entry.status == "failed":
                if resume_failed:
                    result.append(p)
                # else skip failed
            else:
                # in_progress or any other status — re-attempt
                result.append(p)
        return result

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        """Return a summary with total, complete, failed, in_progress counts per agency.

        Returns:
            Dict with ``"totals"`` (overall counts) and ``"by_agency"``
            (per-agency counts).
        """
        totals = {"total": 0, "complete": 0, "failed": 0, "in_progress": 0}
        by_agency: Dict[str, Dict[str, int]] = {}

        for entry in self._documents.values():
            totals["total"] += 1
            totals[entry.status] = totals.get(entry.status, 0) + 1

            if entry.agency not in by_agency:
                by_agency[entry.agency] = {
                    "total": 0, "complete": 0, "failed": 0, "in_progress": 0
                }
            agency_counts = by_agency[entry.agency]
            agency_counts["total"] += 1
            agency_counts[entry.status] = agency_counts.get(entry.status, 0) + 1

        return {"totals": totals, "by_agency": by_agency}

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def compute_file_hash(pdf_path: str) -> str:
        """Compute SHA-256 hash of a file for change detection.

        Reads in 8 KB chunks to handle large files without excessive memory.

        Args:
            pdf_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 digest prefixed with ``sha256:``.
        """
        h = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            while True:
                block = f.read(8192)
                if not block:
                    break
                h.update(block)
        return f"sha256:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# Failure log
# ---------------------------------------------------------------------------

class FailureLog:
    """Append-only JSON log of ingestion failures.

    Each call to :meth:`log_failure` appends an entry to an array stored in
    a JSON file.  This is separate from the manifest and intended for
    post-run review.
    """

    def __init__(self, failures_path: str | Path | None = None):
        """Initialise the failure log.

        Args:
            failures_path: Path to the failures JSON file.  Defaults to
                ``config.FAILURES_PATH``.
        """
        self._path = Path(failures_path) if failures_path is not None else FAILURES_PATH

    def log_failure(
        self,
        pdf_path: str,
        error: str,
        stack_trace: str,
        agency: str,
    ) -> None:
        """Append a failure entry to the failures JSON file.

        Args:
            pdf_path: Path to the PDF that failed.
            error: Short error description.
            stack_trace: Full stack trace.
            agency: Agency identifier.
        """
        entry = {
            "pdf_path": str(Path(pdf_path).resolve()),
            "error": error,
            "stack_trace": stack_trace,
            "agency": agency,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        entries = self.load()
        entries.append(entry)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, default=str)

        logger.warning("Logged failure for %s: %s", pdf_path, error)

    def load(self) -> List[dict]:
        """Load all failure entries from the JSON file.

        Returns:
            List of failure entry dicts.  Empty list if the file does not exist.
        """
        if not self._path.exists():
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)
