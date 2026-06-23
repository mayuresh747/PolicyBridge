"""Kuzu graph database writer for the Seattle Regulatory RAG knowledge graph.

Manages the Kuzu embedded graph database: schema creation, bulk node/edge
loading via COPY FROM DataFrames, incremental updates via MERGE, and Cypher
queries.

The schema has 3 node tables and 9 REL tables:

Node tables:
    AgencyNode  — one per agency (8 total)
    DocumentNode — one per unique source file
    Chunk       — one per ingested chunk (~1500 for the sample)

REL tables (cross-chunk):
    CITES, IMPLEMENTS, DEFINED_BY, SUBJECT_TO, AMENDED_BY, NEXT_SECTION,
    CONFLICTS_WITH

REL tables (hierarchy):
    AGENCY_HAS_DOC  — AgencyNode → DocumentNode
    DOC_HAS_CHUNK   — DocumentNode → Chunk

Classes:
    KuzuWriter: schema creation, bulk loading, incremental updates, queries.

Note:
    Python 3.14 compatibility requires explicit ``dtype='string'`` on all
    string DataFrame columns for COPY FROM (Kuzu's numpy scanner does not
    handle ``object`` dtype on 3.14).  Boolean columns use INT8 instead.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List, Optional

import kuzu
import pandas as pd

from src.config import KUZU_PATH
from src.graph.extractor import Relationship

logger = logging.getLogger(__name__)

# Relationship types supported by the schema.  Used for merge_edge validation
# and get_edge_counts iteration.
VALID_REL_TYPES = frozenset({
    "CITES",
    "IMPLEMENTS",
    "DEFINED_BY",
    "SUBJECT_TO",
    "AMENDED_BY",
    "NEXT_SECTION",
    "CONFLICTS_WITH",
    "AGENCY_HAS_DOC",
    "DOC_HAS_CHUNK",
})

# 6 rule-based cross-chunk REL types (no extra columns beyond confidence)
_RULE_BASED_REL_TYPES = [
    "CITES",
    "IMPLEMENTS",
    "DEFINED_BY",
    "SUBJECT_TO",
    "AMENDED_BY",
    "NEXT_SECTION",
]


class KuzuWriter:
    """Manages Kuzu graph database: schema, bulk loading, incremental updates, queries.

    Usage::

        with KuzuWriter() as writer:
            writer.create_schema()
            writer.load_nodes(chunks_df)
            writer.load_edges(relationships)
            counts = writer.get_edge_counts()
    """

    def __init__(self, db_path: str | Path | None = None):
        """Open (or create) a Kuzu database.

        Args:
            db_path: Directory path for the Kuzu database.  Defaults to
                ``config.KUZU_PATH``.  Kuzu creates the directory if it
                does not already exist.
        """
        self._db_path = Path(db_path) if db_path else KUZU_PATH
        # Ensure the parent directory exists; Kuzu creates the db directory
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(self._db_path))
        self._conn = kuzu.Connection(self._db)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> KuzuWriter:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def create_schema(self) -> None:
        """Create all node tables and REL tables.

        Uses ``IF NOT EXISTS`` so the method is idempotent.

        Node tables: AgencyNode, DocumentNode, Chunk
        REL tables (cross-chunk): CITES, IMPLEMENTS, DEFINED_BY, SUBJECT_TO,
            AMENDED_BY, NEXT_SECTION, CONFLICTS_WITH
        REL tables (hierarchy): AGENCY_HAS_DOC, DOC_HAS_CHUNK

        Note: ``deprecated`` is stored as INT8 (0/1) instead of BOOLEAN
        for Python 3.14 compatibility with Kuzu's numpy scanner.
        """
        # AgencyNode — one per agency (8 total)
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS AgencyNode (
                id STRING PRIMARY KEY,
                label STRING,
                authority_level STRING
            )
        """)
        logger.info("Created/verified AgencyNode table")

        # DocumentNode — one per unique source file
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS DocumentNode (
                id STRING PRIMARY KEY,
                agency STRING,
                label STRING
            )
        """)
        logger.info("Created/verified DocumentNode table")

        # Chunk node table
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Chunk (
                id STRING PRIMARY KEY,
                agency STRING,
                citation STRING,
                section_number STRING,
                authority_level STRING,
                document_type STRING,
                filename STRING,
                chunk_index INT64,
                deprecated INT8 DEFAULT 0
            )
        """)
        logger.info("Created/verified Chunk node table")

        # 6 rule-based cross-chunk REL tables (confidence only)
        for rel_type in _RULE_BASED_REL_TYPES:
            self._conn.execute(f"""
                CREATE REL TABLE IF NOT EXISTS {rel_type} (
                    FROM Chunk TO Chunk,
                    confidence FLOAT DEFAULT 1.0
                )
            """)
            logger.debug("Created/verified REL table: %s", rel_type)

        # CONFLICTS_WITH has extra columns for LLM adjudicator output
        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS CONFLICTS_WITH (
                FROM Chunk TO Chunk,
                confidence FLOAT,
                description STRING,
                resolution STRING
            )
        """)
        logger.info("Created/verified CONFLICTS_WITH REL table")

        # Hierarchy REL tables
        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS AGENCY_HAS_DOC (
                FROM AgencyNode TO DocumentNode,
                confidence FLOAT DEFAULT 1.0
            )
        """)
        logger.info("Created/verified AGENCY_HAS_DOC REL table")

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS DOC_HAS_CHUNK (
                FROM DocumentNode TO Chunk,
                confidence FLOAT DEFAULT 1.0
            )
        """)
        logger.info("Created/verified DOC_HAS_CHUNK REL table")
        logger.info("Schema ready: 3 node tables + 9 REL tables")

    # ------------------------------------------------------------------
    # Bulk loading
    # ------------------------------------------------------------------

    def load_nodes(self, chunks_df: pd.DataFrame) -> int:
        """Bulk-load chunk nodes from a DataFrame via COPY FROM.

        Builds a node DataFrame with the columns expected by the Chunk schema,
        filling missing values (None -> "" for strings, 0 for ints, 0 for
        deprecated).

        Args:
            chunks_df: DataFrame with at least ``id``, ``agency``, ``citation``,
                ``section_number``, ``authority_level``, ``document_type``,
                ``filename``, ``chunk_index`` columns.

        Returns:
            Number of nodes loaded.
        """
        node_df = pd.DataFrame({
            "id": pd.array(
                chunks_df["id"].fillna("").tolist(), dtype="string"
            ),
            "agency": pd.array(
                chunks_df["agency"].fillna("").tolist(), dtype="string"
            ),
            "citation": pd.array(
                chunks_df["citation"].fillna("").tolist(), dtype="string"
            ),
            "section_number": pd.array(
                chunks_df["section_number"].fillna("").tolist(), dtype="string"
            ),
            "authority_level": pd.array(
                chunks_df["authority_level"].fillna("").tolist(), dtype="string"
            ),
            "document_type": pd.array(
                chunks_df.get("document_type", pd.Series(["substantive"] * len(chunks_df)))
                .fillna("substantive").tolist(),
                dtype="string",
            ),
            "filename": pd.array(
                chunks_df["filename"].fillna("").tolist(), dtype="string"
            ),
            "chunk_index": chunks_df["chunk_index"].fillna(0).astype("int64"),
            "deprecated": pd.array(
                [0] * len(chunks_df), dtype="int8"
            ),
        })

        self._conn.execute(
            "COPY Chunk FROM $df", parameters={"df": node_df}
        )
        count = len(node_df)
        logger.info("Loaded %d chunk nodes into Kuzu", count)
        return count

    def load_edges(self, relationships: List[Relationship]) -> dict[str, int]:
        """Bulk-load relationship edges grouped by type via COPY FROM.

        Filters out relationships with empty ``target_id`` (unresolved).

        Args:
            relationships: List of ``Relationship`` objects from the extractor.

        Returns:
            Dict mapping ``rel_type`` -> count of edges loaded.
        """
        # Group by rel_type
        groups: dict[str, list[Relationship]] = {}
        for rel in relationships:
            if not rel.target_id:
                continue  # Skip unresolved
            groups.setdefault(rel.rel_type, []).append(rel)

        counts: dict[str, int] = {}
        for rel_type, rels in groups.items():
            if rel_type not in VALID_REL_TYPES:
                logger.warning("Skipping unknown rel_type: %s", rel_type)
                continue

            edge_df = pd.DataFrame({
                "from_id": pd.array(
                    [r.source_id for r in rels], dtype="string"
                ),
                "to_id": pd.array(
                    [r.target_id for r in rels], dtype="string"
                ),
                "confidence": pd.array(
                    [r.confidence for r in rels], dtype="float64"
                ),
            })

            self._conn.execute(
                f"COPY {rel_type} FROM $df", parameters={"df": edge_df}
            )
            counts[rel_type] = len(rels)
            logger.info("Loaded %d %s edges", len(rels), rel_type)

        return counts

    def load_agency_nodes(self, agency_df: pd.DataFrame) -> int:
        """Bulk-load AgencyNode nodes from a DataFrame via COPY FROM.

        Args:
            agency_df: DataFrame with ``id``, ``label``, ``authority_level`` columns.

        Returns:
            Number of agency nodes loaded.
        """
        node_df = pd.DataFrame({
            "id": pd.array(agency_df["id"].fillna("").tolist(), dtype="string"),
            "label": pd.array(agency_df["label"].fillna("").tolist(), dtype="string"),
            "authority_level": pd.array(
                agency_df["authority_level"].fillna("").tolist(), dtype="string"
            ),
        })
        self._conn.execute("COPY AgencyNode FROM $df", parameters={"df": node_df})
        count = len(node_df)
        logger.info("Loaded %d agency nodes into Kuzu", count)
        return count

    def load_document_nodes(self, doc_df: pd.DataFrame) -> int:
        """Bulk-load DocumentNode nodes from a DataFrame via COPY FROM.

        Args:
            doc_df: DataFrame with ``id``, ``agency``, ``label`` columns.

        Returns:
            Number of document nodes loaded.
        """
        node_df = pd.DataFrame({
            "id": pd.array(doc_df["id"].fillna("").tolist(), dtype="string"),
            "agency": pd.array(doc_df["agency"].fillna("").tolist(), dtype="string"),
            "label": pd.array(doc_df["label"].fillna("").tolist(), dtype="string"),
        })
        self._conn.execute("COPY DocumentNode FROM $df", parameters={"df": node_df})
        count = len(node_df)
        logger.info("Loaded %d document nodes into Kuzu", count)
        return count

    def load_hierarchy_edges(
        self,
        agency_doc_edges: list[tuple[str, str]],
        doc_chunk_edges: list[tuple[str, str]],
    ) -> dict[str, int]:
        """Bulk-load AGENCY_HAS_DOC and DOC_HAS_CHUNK edges via COPY FROM.

        Args:
            agency_doc_edges: List of (agency_id, doc_id) tuples.
            doc_chunk_edges: List of (doc_id, chunk_id) tuples.

        Returns:
            Dict with AGENCY_HAS_DOC and DOC_HAS_CHUNK counts.
        """
        counts: dict[str, int] = {"AGENCY_HAS_DOC": 0, "DOC_HAS_CHUNK": 0}

        if agency_doc_edges:
            ad_df = pd.DataFrame({
                "from_id": pd.array(
                    [e[0] for e in agency_doc_edges], dtype="string"
                ),
                "to_id": pd.array(
                    [e[1] for e in agency_doc_edges], dtype="string"
                ),
                "confidence": pd.array(
                    [1.0] * len(agency_doc_edges), dtype="float64"
                ),
            })
            self._conn.execute(
                "COPY AGENCY_HAS_DOC FROM $df", parameters={"df": ad_df}
            )
            counts["AGENCY_HAS_DOC"] = len(agency_doc_edges)
            logger.info("Loaded %d AGENCY_HAS_DOC edges", len(agency_doc_edges))

        if doc_chunk_edges:
            dc_df = pd.DataFrame({
                "from_id": pd.array(
                    [e[0] for e in doc_chunk_edges], dtype="string"
                ),
                "to_id": pd.array(
                    [e[1] for e in doc_chunk_edges], dtype="string"
                ),
                "confidence": pd.array(
                    [1.0] * len(doc_chunk_edges), dtype="float64"
                ),
            })
            self._conn.execute(
                "COPY DOC_HAS_CHUNK FROM $df", parameters={"df": dc_df}
            )
            counts["DOC_HAS_CHUNK"] = len(doc_chunk_edges)
            logger.info("Loaded %d DOC_HAS_CHUNK edges", len(doc_chunk_edges))

        return counts

    # ------------------------------------------------------------------
    # Incremental updates (MERGE)
    # ------------------------------------------------------------------

    def merge_node(
        self,
        chunk_id: str,
        agency: str,
        citation: str,
        **kwargs,
    ) -> None:
        """Upsert a single chunk node via MERGE (for incremental updates per D-08).

        Args:
            chunk_id: The chunk's unique ID.
            agency: Agency name (e.g., "WAC", "RCW").
            citation: Canonical citation string.
            **kwargs: Optional fields: section_number, authority_level,
                document_type, filename, chunk_index.
        """
        params = {
            "id": chunk_id,
            "agency": agency,
            "citation": citation,
            "section_number": kwargs.get("section_number", ""),
            "authority_level": kwargs.get("authority_level", ""),
            "document_type": kwargs.get("document_type", "substantive"),
            "filename": kwargs.get("filename", ""),
            "chunk_index": kwargs.get("chunk_index", 0),
        }
        self._conn.execute(
            """
            MERGE (c:Chunk {id: $id})
            ON CREATE SET
                c.agency = $agency,
                c.citation = $citation,
                c.section_number = $section_number,
                c.authority_level = $authority_level,
                c.document_type = $document_type,
                c.filename = $filename,
                c.chunk_index = $chunk_index
            """,
            parameters=params,
        )
        logger.debug("Merged node: %s", chunk_id)

    def merge_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        confidence: float = 1.0,
    ) -> None:
        """Upsert a single relationship edge via MERGE (for incremental updates).

        Args:
            source_id: Source chunk ID.
            target_id: Target chunk ID.
            rel_type: Relationship type (must be in VALID_REL_TYPES).
            confidence: Confidence score (default 1.0 for rule-based).

        Raises:
            ValueError: If ``rel_type`` is not in the whitelist.
        """
        if rel_type not in VALID_REL_TYPES:
            raise ValueError(
                f"Invalid rel_type '{rel_type}'. "
                f"Must be one of: {sorted(VALID_REL_TYPES)}"
            )

        # rel_type is interpolated (not parameterized) since Kuzu doesn't
        # support parameterized relationship type names.
        self._conn.execute(
            f"""
            MATCH (a:Chunk {{id: $from_id}}), (b:Chunk {{id: $to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            ON CREATE SET r.confidence = $conf
            """,
            parameters={
                "from_id": source_id,
                "to_id": target_id,
                "conf": confidence,
            },
        )
        logger.debug(
            "Merged %s edge: %s -> %s", rel_type, source_id, target_id
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query(self, cypher: str, params: dict | None = None) -> list[list]:
        """Execute a Cypher query and return results as a list of rows.

        Each row is a list of values (matching the RETURN clause columns).

        Args:
            cypher: Cypher query string.
            params: Optional parameter dict for parameterized queries.

        Returns:
            List of rows, where each row is a list of column values.
        """
        result = self._conn.execute(cypher, parameters=params or {})
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows

    def get_edge_counts(self) -> dict[str, int]:
        """Return a dict of edge counts per relationship type.

        Returns:
            Dict mapping rel_type name -> count of edges.
        """
        counts: dict[str, int] = {}
        for rel_type in VALID_REL_TYPES:
            result = self._conn.execute(
                f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
            )
            if result.has_next():
                row = result.get_next()
                counts[rel_type] = row[0]
            else:
                counts[rel_type] = 0
        return counts

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the Kuzu connection."""
        if self._conn is not None:
            self._conn = None
        if self._db is not None:
            self._db = None

    def destroy(self) -> None:
        """Close the connection and delete the database.

        Handles both Kuzu 0.11.x (single file) and older versions
        (directory-based storage).  Used for ``--mode full`` rebuild per D-08.
        """
        self.close()
        if self._db_path.exists():
            if self._db_path.is_dir():
                shutil.rmtree(self._db_path)
            else:
                self._db_path.unlink()
            logger.info("Destroyed Kuzu database at %s", self._db_path)
