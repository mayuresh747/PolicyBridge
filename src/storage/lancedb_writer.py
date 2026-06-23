"""LanceDB schema and batch writer for the Seattle Regulatory RAG ingestion pipeline.

ChunkRecord: Pydantic LanceModel defining the LanceDB table schema with all
ING-08 metadata fields (citation, section_title, agency, authority_level,
effective_date, is_table, table_type, content_type, key_terms, etc.).

LanceDBWriter: connection manager with table creation, batch insert, record
counting, and index creation (IVF_PQ vector + tantivy BM25 FTS).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import List, Optional

import lancedb
from lancedb.pydantic import LanceModel, Vector

from src.chunkers.base import ChunkData
from src.config import (
    EMBEDDING_DIMENSIONS,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
    VECTOR_INDEX_NUM_PARTITIONS,
    VECTOR_INDEX_NUM_SUB_VECTORS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class ChunkRecord(LanceModel):
    """LanceDB table schema for regulatory document chunks.

    Every field maps to a column in the LanceDB Arrow table.  Complex types
    (lists, dicts) are serialized to JSON strings to stay within Arrow/tantivy
    constraints.
    """

    # Identity
    id: str
    text: str
    embedding: Vector(3072)  # text-embedding-3-large dimension

    # Source metadata
    agency: str
    document_type: str = "substantive"
    filename: str = ""

    # Legal hierarchy
    citation: str = ""
    section_number: Optional[str] = None
    subsection_id: Optional[str] = None
    section_title: Optional[str] = None
    authority_level: str = ""
    jurisdiction: str = "washington"

    # Effective dates
    effective_date: Optional[str] = None
    last_amended_date: Optional[str] = None

    # Structure
    is_table: bool = False
    table_type: Optional[str] = None
    parent_section: Optional[str] = None
    chunk_index: int = 0  # Ordinal position within document for adjacency queries

    # Content classification
    content_type: Optional[str] = None
    key_terms: Optional[str] = None  # JSON-serialized list

    # Image detection
    has_images: bool = False  # True if source page contained images

    # Agency-specific metadata (JSON-serialized dict)
    metadata_json: Optional[str] = None  # e.g. part_group, chapter, ordinance_history

    # Data quality
    is_scanned: bool = False
    ocr_confidence: Optional[float] = None

    # Versioning
    version: int = 1
    deprecated: bool = False
    created_at: str = ""


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class LanceDBWriter:
    """Manages a LanceDB connection and provides batch insert + index helpers.

    Usage::

        writer = LanceDBWriter()
        writer.create_table()
        writer.write_batch(chunks, embeddings)
        # ... more batches ...
        writer.create_vector_index()
        writer.create_fts_index()
    """

    def __init__(self, db_path: str | Path | None = None):
        """Connect to LanceDB at the given path.

        Args:
            db_path: Directory for the LanceDB database.  Defaults to
                ``config.LANCEDB_PATH``.
        """
        self._db_path = Path(db_path) if db_path is not None else LANCEDB_PATH
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))
        self._table = None
        self._table_name = LANCEDB_TABLE_NAME

    # ------------------------------------------------------------------
    # Table lifecycle
    # ------------------------------------------------------------------

    def create_table(self) -> None:
        """Create the chunks table using ``ChunkRecord`` schema.

        If the table already exists it is opened instead.
        """
        try:
            self._table = self._db.create_table(
                self._table_name, schema=ChunkRecord
            )
            logger.info("Created LanceDB table '%s'", self._table_name)
        except Exception:
            # Table already exists — open it
            self._table = self._db.open_table(self._table_name)
            logger.info("Opened existing LanceDB table '%s'", self._table_name)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def write_batch(
        self,
        chunks: List[ChunkData],
        embeddings: List[List[float]],
    ) -> int:
        """Convert ``ChunkData`` + embeddings to ``ChunkRecord`` dicts and batch insert.

        Args:
            chunks: List of ``ChunkData`` objects from the chunking pipeline.
            embeddings: Parallel list of embedding vectors (each 3072-dim).

        Returns:
            The number of records inserted.

        Raises:
            RuntimeError: If ``create_table`` has not been called yet.
        """
        if self._table is None:
            raise RuntimeError(
                "Table not initialised. Call create_table() first."
            )

        now = datetime.datetime.utcnow().isoformat()
        records: list[dict] = []

        for chunk, embedding in zip(chunks, embeddings):
            # Serialize agency-specific metadata dict (preserves all extras)
            extra_meta = {k: v for k, v in chunk.metadata.items() if k != "document_type"}
            metadata_json = json.dumps(extra_meta, ensure_ascii=False) if extra_meta else None

            record = {
                "id": chunk.id,
                "text": chunk.text,
                "embedding": embedding,
                "agency": chunk.agency,
                "document_type": chunk.metadata.get("document_type", "substantive"),
                "filename": chunk.filename,
                "citation": chunk.citation,
                "section_number": chunk.section_number,
                "subsection_id": chunk.subsection_id,
                "section_title": chunk.section_title,
                "authority_level": chunk.authority_level,
                "jurisdiction": chunk.jurisdiction,
                "effective_date": chunk.effective_date,
                "last_amended_date": chunk.last_amended_date,
                "is_table": chunk.is_table,
                "table_type": chunk.table_type,
                "parent_section": chunk.parent_section,
                "chunk_index": chunk.chunk_index,
                "content_type": chunk.content_type,
                "key_terms": chunk.key_terms,
                "has_images": chunk.has_images,
                "metadata_json": metadata_json,
                "is_scanned": chunk.is_scanned,
                "ocr_confidence": chunk.ocr_confidence,
                "version": 1,
                "deprecated": False,
                "created_at": now,
            }
            records.append(record)

        self._table.add(records)
        logger.debug("Inserted %d records into '%s'", len(records), self._table_name)
        return len(records)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_count(self) -> int:
        """Return total number of records in the table."""
        if self._table is None:
            raise RuntimeError(
                "Table not initialised. Call create_table() first."
            )
        return self._table.count_rows()

    # ------------------------------------------------------------------
    # Index creation (call AFTER all inserts)
    # ------------------------------------------------------------------

    def create_vector_index(self) -> None:
        """Create IVF_PQ vector index with cosine metric.

        Uses ``num_partitions=256`` and ``num_sub_vectors=96`` as configured.
        **Must be called AFTER all data is inserted** — building the index on
        incomplete data yields poor recall.
        """
        if self._table is None:
            raise RuntimeError(
                "Table not initialised. Call create_table() first."
            )
        self._table.create_index(
            metric="cosine",
            vector_column_name="embedding",
            num_partitions=VECTOR_INDEX_NUM_PARTITIONS,   # 256
            num_sub_vectors=VECTOR_INDEX_NUM_SUB_VECTORS,  # 96
        )
        logger.info(
            "Created vector index (cosine, %d partitions, %d sub-vectors)",
            VECTOR_INDEX_NUM_PARTITIONS,
            VECTOR_INDEX_NUM_SUB_VECTORS,
        )

    def create_fts_index(self) -> None:
        """Create tantivy-based BM25 full-text search index on the ``text`` column.

        Uses the ``en_stem`` tokenizer for English stemming.  ``replace=True``
        ensures re-runs overwrite any existing FTS index.
        **Must be called AFTER all data is inserted.**
        """
        if self._table is None:
            raise RuntimeError(
                "Table not initialised. Call create_table() first."
            )
        self._table.create_fts_index(
            "text",
            use_tantivy=True,
            tokenizer_name="en_stem",
            replace=True,
        )
        logger.info("Created FTS index (tantivy, en_stem tokenizer)")
