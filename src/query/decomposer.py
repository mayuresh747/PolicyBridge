"""RT-RAG binary tree decomposer for L3+ queries.

Implements the RT-RAG algorithm (adapted from arxiv:2601.11255):
1. Structure analysis — extract core query, known/unknown entities, intent
2. 3-tree generation — parallel LLM calls producing candidate binary trees
3. Consensus selection — pick tree with most common (depth, leaf_count) signature
4. Post-order traversal — solve leaves via retrieve(), propagate answers upward
5. Placeholder propagation — substitute [answer_left] tokens in sequential nodes

Public API:
    decompose_query() — decompose L3+ query into binary reasoning tree
    solve_tree() — solve a decomposition tree via post-order traversal
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

from src.config import LEVEL_MAX_DEPTH, MAX_RETRIEVAL_CALLS, QUERY_LLM_MODEL
from src.query.models import TreeNode
from src.retrieval import RetrievalResult, retrieve

if TYPE_CHECKING:
    from src.query.llm import LLMCallManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

STRUCTURE_ANALYSIS_PROMPT = """\
Analyze this regulatory query and extract its structure:

Query: {query}

Return JSON:
{{
  "core_query": "the main question being asked",
  "known_entities": ["specific codes, agencies, or sections mentioned"],
  "unknown_entities": ["what needs to be found"],
  "intent": "lookup / comparison / conditional / hypothetical"
}}"""

TREE_GENERATION_PROMPT = """\
Decompose this regulatory query into a binary reasoning tree.

Query: {query}
Structure Analysis:
- Core query: {core_query}
- Known entities: {known_entities}
- Unknown entities: {unknown_entities}
- Intent: {intent}

Node types:
- "leaf": Directly answerable with a single search. Contains a specific, self-contained question.
- "sequential": Right child depends on left child's answer. Right query contains [answer_left] placeholder.
- "parallel": Children are independent and can be answered simultaneously.

Rules:
- Maximum tree height: {max_height}
- Each leaf must be answerable with ONE search query
- Use "sequential" when the answer to one question changes what you need to ask next
- Use "parallel" when questions are independent
- Leaf queries should include relevant agency names (SMC, RCW, WAC, DIR) when known

Legal domain examples:
1. "What are the downtown exemption rules AND can the Director waive them?"
   -> parallel: left="Downtown parking exemption rules SMC", right=sequential(left="SDCI Director waiver authority DIR", right="Can Director waive [answer_left]?")

2. "What setback applies to my R1 zone lot if it's a corner lot?"
   -> sequential: left="SMC setback requirements R1 zone", right="Corner lot exceptions to [answer_left]"

Return JSON tree:
{{
  "node_type": "parallel",
  "query": "Merge: downtown exemptions + waiver authority",
  "left": {{"node_type": "leaf", "query": "Downtown parking exemption rules SMC"}},
  "right": {{"node_type": "leaf", "query": "SDCI Director waiver authority DIR"}}
}}"""

# ---------------------------------------------------------------------------
# Tree parsing and manipulation helpers
# ---------------------------------------------------------------------------


def _parse_tree_json(tree_json: dict, fallback_query: str = "original query") -> TreeNode:
    """Recursively parse a JSON dict into a TreeNode.

    Args:
        tree_json: Dict with keys node_type, query, and optionally left/right.
        fallback_query: Query text for the fallback leaf node if parsing fails.

    Returns:
        A TreeNode. On malformed input, returns a single leaf node as fallback.
    """
    try:
        node_type = tree_json.get("node_type", "leaf")
        query = tree_json.get("query", fallback_query)

        # Validate node_type
        if node_type not in ("sequential", "parallel", "leaf"):
            node_type = "leaf"

        left_json = tree_json.get("left")
        right_json = tree_json.get("right")

        left = _parse_tree_json(left_json, fallback_query) if left_json and isinstance(left_json, dict) else None
        right = _parse_tree_json(right_json, fallback_query) if right_json and isinstance(right_json, dict) else None

        return TreeNode(
            node_type=node_type,
            query=query,
            left=left,
            right=right,
            answer=None,
        )
    except Exception:
        logger.warning("Failed to parse tree JSON, returning fallback leaf node")
        return TreeNode(
            node_type="leaf",
            query=fallback_query,
            left=None,
            right=None,
            answer=None,
        )


def _tree_depth(node: TreeNode) -> int:
    """Calculate the depth (height) of a tree.

    A single leaf has depth 1. An internal node's depth is 1 + max(children).
    """
    if node.is_leaf():
        return 1
    left_d = _tree_depth(node.left) if node.left else 0
    right_d = _tree_depth(node.right) if node.right else 0
    return 1 + max(left_d, right_d)


def _tree_signature(node: TreeNode) -> tuple[int, int]:
    """Return (depth, leaf_count) signature for consensus comparison."""
    return (_tree_depth(node), node.leaf_count)


def _select_consensus(trees: list[TreeNode]) -> TreeNode:
    """Select the consensus tree from a list of candidates.

    Picks the tree whose (depth, leaf_count) signature appears most frequently.
    If all signatures are unique, returns the first tree.

    Args:
        trees: List of candidate TreeNode trees.

    Returns:
        The selected consensus tree.
    """
    if not trees:
        raise ValueError("Cannot select consensus from empty tree list")

    if len(trees) == 1:
        return trees[0]

    # Compute signatures
    signatures = [_tree_signature(t) for t in trees]

    # Count frequency of each signature
    sig_counts: dict[tuple[int, int], int] = {}
    for sig in signatures:
        sig_counts[sig] = sig_counts.get(sig, 0) + 1

    # Find the most common signature
    max_count = max(sig_counts.values())

    if max_count == 1:
        # All unique — return first tree
        return trees[0]

    # Find the most common signature (first one if tie)
    best_sig = None
    for sig in signatures:
        if sig_counts[sig] == max_count:
            best_sig = sig
            break

    # Return the first tree with the best signature
    for tree, sig in zip(trees, signatures):
        if sig == best_sig:
            return tree

    return trees[0]


def _truncate_tree(node: TreeNode, max_height: int = 3, current_depth: int = 0) -> TreeNode:
    """Truncate a tree to enforce maximum height.

    Nodes at the maximum depth that are not leaves are converted to leaf nodes
    (their children are dropped).

    Args:
        node: The tree node to truncate.
        max_height: Maximum allowed tree height.
        current_depth: Current depth in the tree (0-based, root = 0).

    Returns:
        The (possibly) truncated tree.
    """
    # current_depth is 0-based, so at depth (max_height - 1) we are at the last
    # allowed level => this node must be a leaf or we convert it.
    if current_depth >= max_height - 1:
        # Force this node to be a leaf
        if not node.is_leaf():
            logger.info(
                "Truncating tree at depth %d: converting '%s' node to leaf",
                current_depth, node.node_type,
            )
            return TreeNode(
                node_type="leaf",
                query=node.query,
                left=None,
                right=None,
                answer=None,
            )
        return node

    # Recursively truncate children
    new_left = _truncate_tree(node.left, max_height, current_depth + 1) if node.left else None
    new_right = _truncate_tree(node.right, max_height, current_depth + 1) if node.right else None

    return TreeNode(
        node_type=node.node_type,
        query=node.query,
        left=new_left,
        right=new_right,
        answer=node.answer,
    )


# ---------------------------------------------------------------------------
# Structure analysis
# ---------------------------------------------------------------------------


async def _analyze_structure(query: str, llm: LLMCallManager) -> dict:
    """Extract structure from the query via LLM.

    Returns a dict with keys: core_query, known_entities, unknown_entities, intent.
    """
    messages = [
        {"role": "system", "content": "You are a regulatory query analyzer. Return valid JSON only."},
        {"role": "user", "content": STRUCTURE_ANALYSIS_PROMPT.format(query=query)},
    ]

    response = await llm.call(
        model=QUERY_LLM_MODEL,
        messages=messages,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        structure = json.loads(response)
        # Ensure required keys
        return {
            "core_query": structure.get("core_query", query),
            "known_entities": structure.get("known_entities", []),
            "unknown_entities": structure.get("unknown_entities", []),
            "intent": structure.get("intent", "lookup"),
        }
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse structure analysis response, using defaults")
        return {
            "core_query": query,
            "known_entities": [],
            "unknown_entities": [],
            "intent": "lookup",
        }


# ---------------------------------------------------------------------------
# Tree generation
# ---------------------------------------------------------------------------


async def _generate_tree(query: str, structure: dict, llm: LLMCallManager, max_height: int = 3) -> TreeNode:
    """Generate a single candidate binary tree via LLM.

    Args:
        query: The original user query.
        structure: Output from _analyze_structure.
        llm: The LLM call manager.
        max_height: Maximum allowed tree height (passed through to prompt).

    Returns:
        A parsed TreeNode.
    """
    prompt = TREE_GENERATION_PROMPT.format(
        query=query,
        core_query=structure["core_query"],
        known_entities=", ".join(structure["known_entities"]) if structure["known_entities"] else "none",
        unknown_entities=", ".join(structure["unknown_entities"]) if structure["unknown_entities"] else "none",
        intent=structure["intent"],
        max_height=max_height,
    )

    messages = [
        {"role": "system", "content": "You are a regulatory query decomposer. Return valid JSON only."},
        {"role": "user", "content": prompt},
    ]

    response = await llm.call(
        model=QUERY_LLM_MODEL,
        messages=messages,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        tree_json = json.loads(response)
        return _parse_tree_json(tree_json, fallback_query=query)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse tree generation response, returning leaf fallback")
        return TreeNode(
            node_type="leaf",
            query=query,
            left=None,
            right=None,
            answer=None,
        )


# ---------------------------------------------------------------------------
# Public API: decompose_query
# ---------------------------------------------------------------------------


async def decompose_query(query: str, level: str, llm: LLMCallManager) -> TreeNode:
    """Decompose L3+ query into binary reasoning tree using RT-RAG.

    Algorithm:
    1. Structure analysis via GPT-4.1-mini
    2. Generate 3 candidate trees (temp=0.0 for consistency)
    3. Select consensus tree (most common depth+leaf pattern)
    4. Validate and truncate to level-appropriate max height

    Max height per level (LEVEL_MAX_DEPTH): L3→3, L4→4, L5→4, L6→3.
    L6 stays at 3 — premise queries don't benefit from deep decomposition.

    Args:
        query: The user's original query text.
        level: Complexity level ("L3" through "L6").
        llm: The shared LLM call manager.

    Returns:
        A TreeNode representing the decomposition tree.
    """
    max_height = LEVEL_MAX_DEPTH.get(level, 3)

    # Step 1: Structure analysis
    structure = await _analyze_structure(query, llm)
    logger.info("Structure analysis: %s", structure)

    # Step 2: Generate 3 candidate trees in parallel
    tree_coros = [_generate_tree(query, structure, llm, max_height=max_height) for _ in range(3)]
    candidate_trees = await asyncio.gather(*tree_coros)

    logger.info(
        "Generated %d candidate trees with signatures: %s (max_height=%d for %s)",
        len(candidate_trees),
        [_tree_signature(t) for t in candidate_trees],
        max_height,
        level,
    )

    # Step 3: Consensus selection
    selected = _select_consensus(list(candidate_trees))
    logger.info("Selected consensus tree: signature=%s", _tree_signature(selected))

    # Step 4: Truncate to level-appropriate max height
    truncated = _truncate_tree(selected, max_height=max_height)

    return truncated


# ---------------------------------------------------------------------------
# Tree solving: post-order traversal
# ---------------------------------------------------------------------------


def _format_leaf_answer(results: list[RetrievalResult]) -> str:
    """Format retrieval results into a brief answer string for a leaf node.

    Concatenates top-3 result excerpts (first 200 chars each).
    """
    if not results:
        return "No relevant results found."

    excerpts = []
    for r in results[:3]:
        excerpt = r.text[:200].strip()
        excerpts.append(f"[{r.citation}] {excerpt}")

    return " | ".join(excerpts)


async def _generate_leaf_answer(
    query: str,
    results: list[RetrievalResult],
    llm: LLMCallManager,
) -> str:
    """Generate a concise LLM answer for a leaf node query.

    Calls gpt-4.1-mini with the top 5 chunk texts as context. Falls back
    to snippet concatenation (_format_leaf_answer) if the LLM call fails.

    Args:
        query: The leaf node's sub-query.
        results: Retrieved chunks for this leaf.
        llm: Shared LLMCallManager instance.

    Returns:
        A 2-3 sentence answer string.
    """
    if not results:
        return "No relevant results found."

    top_chunks = results[:5]
    sources_text = "\n\n".join(
        f"[{i + 1}] {r.citation}\n{r.text[:500]}"
        for i, r in enumerate(top_chunks)
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a legal research assistant. Answer the question concisely "
                "using only the provided sources. 2-3 sentences maximum."
            ),
        },
        {
            "role": "user",
            "content": f"Sources:\n{sources_text}\n\nQuestion: {query}",
        },
    ]

    try:
        answer = await llm.call(
            model=QUERY_LLM_MODEL,
            messages=messages,
            temperature=0.1,
        )
        return answer or _format_leaf_answer(results)
    except Exception as exc:
        logger.warning("Leaf answer LLM call failed, using snippet fallback: %s", exc)
        return _format_leaf_answer(results)


async def _solve_leaf(
    node: TreeNode,
    agency_filter: list[str] | None,
    retrieval_count: list[int],
    llm: LLMCallManager,
    leaf_stats: list[dict] | None = None,
) -> list[RetrievalResult]:
    """Solve a leaf node by calling retrieve().

    Args:
        node: The leaf TreeNode.
        agency_filter: Optional agency filter for retrieval.
        retrieval_count: Mutable list[int] tracking total retrieve() calls.
        llm: Shared LLMCallManager instance for generating leaf answers.
        leaf_stats: Optional mutable list to append per-leaf retrieval stats.

    Returns:
        List of RetrievalResult from retrieve().
    """
    if retrieval_count[0] >= MAX_RETRIEVAL_CALLS:
        logger.warning(
            "MAX_RETRIEVAL_CALLS (%d) reached, skipping leaf: %s",
            MAX_RETRIEVAL_CALLS, node.query[:80],
        )
        node.answer = "Retrieval limit reached — could not retrieve for this sub-query."
        return []

    retrieval_count[0] += 1
    # Phase 8 (08-04): ask retrieve() for the query_vec it already computes
    # inside vector_search so downstream S3 seed fusion can reuse it without
    # a second embed call (D-06 binding). On failure query_vec is None and
    # the leaf is skipped from the composite-vector average in fuse_seeds.
    retrieve_out = await asyncio.to_thread(
        retrieve, node.query, agency_filter, return_query_vec=True,
    )
    if isinstance(retrieve_out, tuple) and len(retrieve_out) == 2:
        results, query_vec = retrieve_out
    else:
        # Defensive: if retrieve() fell back to the legacy single-return
        # shape for any reason, still populate results and set query_vec None.
        results = retrieve_out if isinstance(retrieve_out, list) else []
        query_vec = None

    # Cache on the leaf node so pipeline.py S3 branch can read without
    # re-embedding. Internal nodes never carry these.
    node.query_vec = query_vec
    node.retrieval_results = list(results)

    node.answer = await _generate_leaf_answer(node.query, results, llm)

    if leaf_stats is not None:
        leaf_stats.append({
            "leaf_query": node.query,
            "chunk_count": len(results),
            "methods": {
                "vector": sum(1 for r in results if "vector" in r.retrieval_sources),
                "bm25": sum(1 for r in results if "bm25" in r.retrieval_sources),
            },
            "answer_preview": (node.answer or "")[:200],
            "chunks": [
                {
                    "citation": r.citation,
                    "score": round(r.score, 4),
                    "agency": r.agency,
                    "retrieval_sources": r.retrieval_sources,
                }
                for r in results
            ],
        })

    return results


async def solve_tree(
    tree: TreeNode,
    agency_filter: list[str] | None,
    llm: LLMCallManager,
    _retrieval_count: list[int] | None = None,
    _leaf_stats: list[dict] | None = None,
) -> tuple[list[RetrievalResult], str, list[dict]]:
    """Solve a decomposition tree via post-order traversal.

    Returns (all_retrieval_results, combined_answer_text, leaf_stats).

    Leaf nodes: call retrieve() and format answer from results.
    Sequential nodes: solve left, substitute [answer_left] in right query, solve right.
    Parallel nodes: solve both children concurrently via asyncio.gather().

    Safety: MAX_RETRIEVAL_CALLS limit (default 8) prevents runaway decomposition.

    Args:
        tree: The root TreeNode of the decomposition tree.
        agency_filter: Optional agency filter passed to retrieve().
        llm: The shared LLM call manager.
        _retrieval_count: Internal counter for retrieval calls (do not pass externally).
        _leaf_stats: Internal accumulator for per-leaf stats (do not pass externally).

    Returns:
        Tuple of (all_retrieval_results, combined_answer_text, leaf_stats).
    """
    if _retrieval_count is None:
        _retrieval_count = [0]
    if _leaf_stats is None:
        _leaf_stats = []

    all_results: list[RetrievalResult] = []

    if tree.is_leaf():
        results = await _solve_leaf(tree, agency_filter, _retrieval_count, llm, _leaf_stats)
        all_results.extend(results)

    elif tree.node_type == "sequential":
        # Solve left first
        left_results, left_answer, _ = await solve_tree(
            tree.left, agency_filter, llm, _retrieval_count, _leaf_stats,
        )
        all_results.extend(left_results)

        # Substitute [answer_left] in right child's query
        if tree.right is not None:
            left_answer_truncated = left_answer[:500] if left_answer else ""
            tree.right.query = tree.right.query.replace(
                "[answer_left]", left_answer_truncated,
            )
            # Also propagate into any nested nodes that might contain the placeholder
            _propagate_placeholder(tree.right, "[answer_left]", left_answer_truncated)

        # Solve right
        right_results, right_answer, _ = await solve_tree(
            tree.right, agency_filter, llm, _retrieval_count, _leaf_stats,
        )
        all_results.extend(right_results)

        tree.answer = f"{left_answer}\n\n{right_answer}"

    elif tree.node_type == "parallel":
        # Solve both children concurrently
        left_coro = solve_tree(tree.left, agency_filter, llm, _retrieval_count, _leaf_stats)
        right_coro = solve_tree(tree.right, agency_filter, llm, _retrieval_count, _leaf_stats)
        (left_results, left_answer, _), (right_results, right_answer, _) = await asyncio.gather(
            left_coro, right_coro,
        )
        all_results.extend(left_results)
        all_results.extend(right_results)

        tree.answer = f"{left_answer}\n\n{right_answer}"

    else:
        # Unknown node type — treat as leaf
        logger.warning("Unknown node type '%s', treating as leaf", tree.node_type)
        results = await _solve_leaf(tree, agency_filter, _retrieval_count, llm, _leaf_stats)
        all_results.extend(results)

    # Final answer text
    answer_text = tree.answer or ""

    # Post-traversal check: scan for leaked placeholder tokens
    if _retrieval_count is not None and re.search(r"\[answer_", answer_text):
        logger.warning(
            "Leaked placeholder tokens detected in answer, cleaning up: %s",
            re.findall(r"\[answer_\w+\]", answer_text),
        )
        # Remove leaked placeholders
        answer_text = re.sub(r"\[answer_\w+\]", "", answer_text).strip()
        tree.answer = answer_text

    return all_results, answer_text, _leaf_stats


def _propagate_placeholder(node: TreeNode, placeholder: str, replacement: str) -> None:
    """Recursively replace a placeholder in all descendant queries.

    This handles the case where a sequential node's placeholder appears
    deeper in its right subtree.
    """
    if node is None:
        return
    if node.left is not None:
        node.left.query = node.left.query.replace(placeholder, replacement)
        _propagate_placeholder(node.left, placeholder, replacement)
    if node.right is not None:
        node.right.query = node.right.query.replace(placeholder, replacement)
        _propagate_placeholder(node.right, placeholder, replacement)
