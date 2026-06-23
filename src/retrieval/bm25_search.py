"""LanceDB native FTS (BM25) search with optional agency pre-filtering.

Uses LanceDB's native full-text search (``query_type="fts"``) rather than
the tantivy backend.  Automatically creates the FTS index on first use
(per RESEARCH.md pitfall #1).
"""

import logging

import pandas as pd

from src.config import BM25_TOP_K, VALID_AGENCIES

logger = logging.getLogger(__name__)

_fts_index_ensured = False


def ensure_fts_index(table) -> None:
    """Create native FTS index if not already present.  Idempotent.

    Called once per process on the first ``bm25_search`` invocation.
    Uses ``replace=True`` so re-runs are safe.

    Args:
        table: An opened LanceDB table.
    """
    global _fts_index_ensured
    if not _fts_index_ensured:
        try:
            table.create_fts_index("text", replace=True)
            _fts_index_ensured = True
        except Exception as e:
            logger.warning("FTS index creation failed: %s", e)


def bm25_search(
    table,
    query: str,
    agency_filter: list[str] | None = None,
    top_k: int = BM25_TOP_K,
) -> pd.DataFrame:
    """Execute BM25 keyword search on a LanceDB table using native FTS.

    CRITICAL: Uses native FTS (not tantivy).  Calls
    ``create_fts_index('text', replace=True)`` on first use to ensure the
    index exists (per RESEARCH.md pitfall #1).

    Args:
        table: An opened LanceDB table.
        query: Natural language query string.
        agency_filter: Optional list of agency names to restrict results.
            None means all agencies are searched (per D-08).
        top_k: Maximum number of results to return.

    Returns:
        DataFrame with ChunkRecord columns plus ``_score``
        (descending = better, i.e., higher score = more relevant).
        Returns an empty DataFrame if the query produces no FTS matches
        or if an error occurs.
    """
    ensure_fts_index(table)

    if not query or not query.strip():
        return pd.DataFrame()

    try:
        search = table.search(query, query_type="fts").limit(top_k)

        if agency_filter:
            valid = [a for a in agency_filter if a in VALID_AGENCIES]
            if valid:
                agencies_str = ", ".join(f"'{a}'" for a in valid)
                search = search.where(f"agency IN ({agencies_str})", prefilter=True)

        results = search.to_pandas()
        return results
    except Exception as e:
        logger.warning("BM25 search failed (returning empty): %s", e)
        return pd.DataFrame()
