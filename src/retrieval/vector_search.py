"""LanceDB vector search with optional agency pre-filtering.

Embeds the query using OpenAI text-embedding-3-large, then performs cosine
similarity search on the LanceDB chunks table.  Supports agency filtering
to scope results to specific regulatory sources.

Per D-05 (Phase 8): the function can optionally return the query embedding
it already computes, so downstream consumers (beam traversal, seed fusion)
can reuse it without a second ``embed_texts`` call.
"""

import logging

import numpy as np
import pandas as pd

from src.config import VALID_AGENCIES, VECTOR_TOP_K
from src.embeddings.openai_embedder import embed_texts_sync

logger = logging.getLogger(__name__)


def vector_search(
    table,
    query: str,
    agency_filter: list[str] | None = None,
    top_k: int = VECTOR_TOP_K,
    return_query_vec: bool = False,
) -> "pd.DataFrame | tuple[pd.DataFrame, np.ndarray]":
    """Execute cosine similarity search on a LanceDB table.

    Embeds the query string using ``embed_texts_sync``, then searches the
    table for the nearest chunks by cosine distance.

    Args:
        table: An opened LanceDB table (e.g., ``db.open_table("chunks")``).
        query: Natural language query string.
        agency_filter: Optional list of agency names to restrict results.
            None means all agencies are searched (per D-08).
            Agency names are validated against ``VALID_AGENCIES`` before use
            (per pitfall #4 in RESEARCH.md).
        top_k: Maximum number of results to return.
        return_query_vec: When True, returns ``(DataFrame, query_vec)`` where
            ``query_vec`` is the L2-normalized ``np.float32`` embedding used
            for the search.  Defaults to False so legacy callers keep the
            DataFrame-only return shape unchanged (non-breaking).

            This kwarg exists so hybrid.retrieve() can feed the already-
            computed query vector straight into the S2 beam traversal
            without issuing a second embedding call (D-05 binding).

    Returns:
        DataFrame with ChunkRecord columns plus ``_distance`` (ascending =
        better, lower distance = more similar).  If
        ``return_query_vec=True``, returns a 2-tuple of (DataFrame,
        np.ndarray) where the ndarray has shape ``(EMBEDDING_DIMENSIONS,)``.
    """
    embedding = embed_texts_sync([query])[0]

    search = table.search(embedding).distance_type("cosine").limit(top_k)

    if agency_filter:
        # Validate agencies against known set (pitfall #4: prevent SQL injection)
        valid = [a for a in agency_filter if a in VALID_AGENCIES]
        if valid:
            agencies_str = ", ".join(f"'{a}'" for a in valid)
            search = search.where(f"agency IN ({agencies_str})")

    results = search.to_pandas()

    if not return_query_vec:
        return results

    # Normalize to unit length for downstream cosine scoring.
    qvec = np.asarray(embedding, dtype=np.float32)
    n = float(np.linalg.norm(qvec))
    qvec_norm = qvec / n if n > 0 else qvec
    return results, qvec_norm
