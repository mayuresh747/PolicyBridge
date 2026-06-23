"""Phase 4 data models for the query pipeline.

Defines all shared types used across classifier, decomposer, synthesizer,
and session management. These are the contracts between pipeline stages.

FALLBACK: This file may be created by parallel Plan 04-01 agent.
Defines locally for Plan 04-04 if not yet available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


@dataclass
class ClassificationResult:
    """Output of the query complexity classifier (D-01, D-03).

    Attributes:
        level: Complexity level "L1" through "L6".
        premise_scan_needed: Whether the query may contain a false premise.
        reasoning: Brief explanation of the classification.
    """

    level: str
    premise_scan_needed: bool
    reasoning: str
    conflict_seeking: bool = False


@dataclass
class TreeNode:
    """Binary tree node for RT-RAG query decomposition.

    node_type is one of: "sequential", "parallel", "leaf".
    Leaf nodes hold the actual sub-query text. Internal nodes combine
    child results via sequential (left-then-right) or parallel execution.

    Attributes:
        node_type: "sequential", "parallel", or "leaf".
        query: The (sub-)query text for this node.
        left: Left child node, or None for leaf nodes.
        right: Right child node, or None for leaf nodes.
        answer: Filled after retrieval + synthesis for this node.
    """

    node_type: str
    query: str
    left: TreeNode | None
    right: TreeNode | None
    answer: str | None
    # Phase 8 (08-04): per-leaf cache populated during solve_tree.
    # Enables S3 seed fusion to reuse the per-leaf query embedding and
    # top seed chunk_ids without re-embedding or re-retrieving. Set only
    # on leaf nodes; internal nodes leave these at default None/empty list.
    query_vec: "np.ndarray | None" = None
    retrieval_results: list[Any] = field(default_factory=list)

    def is_leaf(self) -> bool:
        """Return True if this is a leaf node (no children)."""
        return self.left is None and self.right is None

    def leaves(self) -> list[TreeNode]:
        """Collect all leaf nodes in left-to-right order."""
        if self.is_leaf():
            return [self]
        result: list[TreeNode] = []
        if self.left is not None:
            result.extend(self.left.leaves())
        if self.right is not None:
            result.extend(self.right.leaves())
        return result

    @property
    def leaf_count(self) -> int:
        """Return the number of leaf nodes in this subtree."""
        return len(self.leaves())


@dataclass
class SourceRef:
    """Mapping from a retrieved chunk to its display + citation metadata.

    The LLM cites facts inline using `[{citation}]` (the bracketed citation
    string). `source_num` is retained as the 1..N ordinal used by the
    sidebar's numbered manifest, but is not part of the LLM-facing format.

    Attributes:
        source_num: 1..N ordinal for sidebar enumeration only.
        citation: Human-readable citation (e.g., "SMC 23.44.014(B)").
        agency: Source agency code (e.g., "SMC").
        authority_level: Legal authority classification.
        page: Page number from chunk metadata, if available.
        chunk_id: LanceDB chunk identifier.
        score: RRF retrieval score.
        text_excerpt: Verbatim text excerpt from the chunk.
    """

    source_num: int
    citation: str
    agency: str
    authority_level: str
    page: int | None
    chunk_id: str
    score: float
    text_excerpt: str


@dataclass
class ClaimResult:
    """A single claim in the synthesized answer with confidence metadata.

    Attributes:
        id: Sidebar ordinal of the cited source (SourceRef.source_num).
        citation: The legal citation supporting this claim (the bracket key).
        page: Page number, if available.
        confidence: One of "strongly_supported", "reasonably_inferred", "uncertain".
        excerpt: Verbatim text excerpt from the source chunk.
    """

    id: int
    citation: str
    page: int | None
    confidence: str
    excerpt: str


@dataclass
class AnswerResult:
    """Complete answer from the query pipeline (D-11).

    Attributes:
        answer_text: Prose answer with `[CITATION]` markers (e.g. `[RCW 19.27.074]`).
        claims: Structured per-claim data with confidence levels.
        sources: Full retrieved-chunk manifest (sidebar source list).
        premise_flag: If query had false premise: {premise, correction, source_citation}.
        session_id: Session identifier for multi-turn conversations.
        query_level: Classification level "L1" through "L6".
    """

    answer_text: str
    claims: list[ClaimResult]
    sources: list[SourceRef]
    premise_flag: dict | None
    session_id: str
    query_level: str


@dataclass
class PremiseResult:
    """Result of adversarial premise detection (D-04).

    Attributes:
        has_premise: Whether a potentially false premise was detected.
        premise: The identified premise statement.
        verification_query: Query to verify the premise against real documents.
        correction: Correction text if premise is false, else None.
        source_citation: Citation contradicting the premise, else None.
    """

    has_premise: bool
    premise: str
    verification_query: str
    correction: str | None
    source_citation: str | None
