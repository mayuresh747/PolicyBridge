"""Query pipeline orchestrator -- wires classify -> premise check -> decompose -> retrieve -> synthesize.

This is the top-level integration module for Phase 4. It connects all
pipeline stages into a single async generator that yields SSE events
per D-14 (status, sources, premise_flag, token, usage, session_id, done).

NOTE on D-14 per-sub-query sources: The full D-14 spec shows per-leaf
sources events during tree solving. This implementation emits a single
aggregate sources event after solve_tree() returns for simplicity.
Per-leaf streaming requires a callback architecture that adds complexity
disproportionate to user value (the UI buffers until done anyway per D-15).
This is an intentional simplification -- can be upgraded in a future phase.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import traceback
from collections.abc import AsyncIterator

from src.config import (
    AUTHORITY_HIERARCHY,
    CONFLICT_EXPAND_ENABLED,
    GRAPH_EXPAND_SEEDS,
    GRAPH_FEATURE_COMPOSER,
    GRAPH_FEATURE_DIVERSITY,
    GRAPH_FEATURE_ONDEMAND_RESOLVER,
    GRAPH_FEATURE_SEED_FUSION,
    KUZU_PATH,
    LANCEDB_PATH,
    LANCEDB_TABLE_NAME,
    RETRIEVAL_TOP_K,
    SYNTHESIS_CONTEXT_MAX_TOKENS,
    SYNTHESIS_OVERHEAD_TOKENS,
    SYNTHESIS_TOP_K,
)
from src.query.classifier import classify_query
from src.query.context_builder import build_context, enforce_token_budget, format_sources_summary, count_tokens_for_audit
from src.query.decomposer import decompose_query, solve_tree
from src.query.llm import LLMCallManager
from src.query.models import AnswerResult, PremiseResult
from src.query.premise_detector import scan_premise, verify_premise
from src.query.session import SessionManager, rewrite_follow_up
from src.query.synthesizer import synthesize_answer
from src.retrieval import RetrievalResult, retrieve
from src.retrieval.conflict_expander import expand_conflicts
from src.retrieval.reranker import rerank_by_answer, rerank_by_query
from src.retrieval.graph_expander import expand_by_graph, expand_by_graph_from_query
from src.storage.trace_collector import TraceCollector

logger = logging.getLogger(__name__)

# Module-level singletons (created once, reused across requests)
_llm_manager: LLMCallManager | None = None
_session_manager: SessionManager | None = None

# Phase 8 S10 (08-05): on-demand resolver citation-index cache.
# Built once per server lifetime from the LanceDB chunks table and reused
# for every query — zero LLM / embedding work at query time.
_citation_index_cache: dict[str, str] | None = None
_chapter_index_cache: dict[str, list[str]] | None = None


def _get_citation_indices() -> tuple[dict[str, str], dict[str, list[str]]] | None:
    """Return the cached (citation_index, chapter_index) pair.

    Builds on first call by scanning the LanceDB chunks table (pure
    regex / dict work — no LLM, no embedding). Returns None on any error
    so the caller can treat this as a silent-fallback no-op.
    """
    global _citation_index_cache, _chapter_index_cache
    if _citation_index_cache is not None and _chapter_index_cache is not None:
        return _citation_index_cache, _chapter_index_cache
    try:
        import lancedb  # local import so this module still imports when
                         # LanceDB is not installed (e.g. unit-test env).
        from src.graph.citation_index import build_citation_index

        db = lancedb.connect(str(LANCEDB_PATH))
        table = db.open_table(LANCEDB_TABLE_NAME)
        cit_idx, chap_idx = build_citation_index(table)
        _citation_index_cache, _chapter_index_cache = cit_idx, chap_idx
        return cit_idx, chap_idx
    except Exception as exc:
        logger.debug("on-demand resolver: index build failed: %s", exc)
        return None


def _run_on_demand_resolver(results: list[RetrievalResult]) -> None:
    """Resolve unresolved citations across the shortlist — S10 wiring.

    Iterates the current top results and, for each chunk whose metadata
    carries an ``unresolved_citations`` list (via ``graph_context`` or an
    explicit attribute), calls
    :func:`src.graph.on_demand_resolver.resolve_for_chunk`. Writes are
    idempotent (MERGE). Flag-gated by ``GRAPH_FEATURE_ONDEMAND_RESOLVER``.

    The function is fully silent-fallback: one bad chunk cannot break
    synthesis. If the current chunk schema does not surface
    ``unresolved_citations`` yet, this is a no-op — plumbing the field
    through ingestion is a follow-up plan.
    """
    if not GRAPH_FEATURE_ONDEMAND_RESOLVER or not results:
        return
    try:
        indices = _get_citation_indices()
        if indices is None:
            return
        citation_index, chapter_index = indices

        from src.graph.kuzu_writer import KuzuWriter
        from src.graph.on_demand_resolver import resolve_for_chunk

        if not KUZU_PATH.exists():
            return

        with KuzuWriter(KUZU_PATH) as writer:
            for r in results:
                try:
                    unresolved: list[str] = []
                    # Support two schema shapes without modifying ingestion:
                    # 1. An attribute / dict entry named unresolved_citations
                    # 2. graph_context containing an "unresolved_citations" key
                    raw_attr = getattr(r, "unresolved_citations", None)
                    if isinstance(raw_attr, list):
                        unresolved.extend(str(c) for c in raw_attr if c)
                    if r.graph_context:
                        for ctx in r.graph_context:
                            if isinstance(ctx, dict):
                                found = ctx.get("unresolved_citations")
                                if isinstance(found, list):
                                    unresolved.extend(
                                        str(c) for c in found if c
                                    )
                    if not unresolved:
                        continue
                    resolve_for_chunk(
                        chunk_id=r.chunk_id,
                        unresolved_citations=unresolved,
                        writer=writer,
                        citation_index=citation_index,
                        chapter_index=chapter_index,
                    )
                except Exception as chunk_exc:
                    logger.debug(
                        "on-demand resolver: chunk %s errored: %s",
                        r.chunk_id, chunk_exc,
                    )
                    continue
    except Exception as exc:
        logger.debug("on-demand resolver: outer silent-fallback: %s", exc)


def get_llm_manager() -> LLMCallManager:
    """Get or create the module-level LLMCallManager singleton."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMCallManager()
    return _llm_manager


def get_session_manager() -> SessionManager:
    """Get or create the module-level SessionManager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def _serialize_tree(node, depth: int = 0) -> dict:
    """Recursively serialize a TreeNode to a JSON-safe dict for audit events."""
    result = {
        "node_type": node.node_type,
        "query": node.query,
        "depth": depth,
        "answer": (node.answer or "")[:200] if node.answer else None,
    }
    if node.left is not None:
        result["left"] = _serialize_tree(node.left, depth + 1)
    if node.right is not None:
        result["right"] = _serialize_tree(node.right, depth + 1)
    return result


def _tree_depth(node) -> int:
    """Return the depth of a TreeNode tree."""
    if node is None or node.is_leaf():
        return 0
    return 1 + max(_tree_depth(node.left), _tree_depth(node.right))


async def run_pipeline(
    query: str,
    agency_filter: list[str] | None = None,
    session_id: str | None = None,
    audit_mode: bool = False,
    trace_collector: TraceCollector | None = None,
) -> AsyncIterator[dict]:
    """Run the full query pipeline as an async SSE event generator.

    Event sequence per D-14:
    1. status: "Classifying query..."
    2. status: "Checking premise..." (if needed)
    3. premise_flag: {...} (if false premise detected)
    4. status: "Retrieving..." / "Decomposing into N sub-queries..."
    5. sources: [...] (aggregated after retrieval completes)
    6. status: "Synthesizing answer..."
    7. token: "..." (streamed answer chunks)
    8. usage: {...}
    9. session_id: "..."
    10. done

    Args:
        query: The user's question.
        agency_filter: Optional list of agency codes to scope retrieval.
        session_id: Optional existing session ID for multi-turn.

    Yields:
        Dict events with "type" and "data" keys for SSE streaming.
    """
    llm = get_llm_manager()
    session_mgr = get_session_manager()
    sid, session = await session_mgr.get_or_create(session_id)

    # Update agency filter if provided
    if agency_filter is not None:
        session.agency_filter = agency_filter
    effective_filter = session.agency_filter

    # Rewrite follow-up queries using conversation history (D-18)
    working_query = await rewrite_follow_up(query, session.turns, llm)

    # Step 1: Classify
    yield {"type": "status", "data": "Classifying query..."}
    t0 = time.perf_counter()
    try:
        classification = await classify_query(working_query, llm)
    except Exception as exc:
        logger.exception("Classification failed")
        if audit_mode:
            yield {"type": "audit_error", "data": json.dumps({
                "stage": "classify", "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc()[-500:],
            })}
        # Fallback
        from src.query.classifier import ClassificationResult
        classification = ClassificationResult(level="L2", reasoning="fallback", premise_scan_needed=False, conflict_seeking=False)
    classify_ms = (time.perf_counter() - t0) * 1000
    level = classification.level

    classify_data = {
        "stage": "classify",
        "elapsed_ms": round(classify_ms, 1),
        "input": {"query": working_query},
        "output": {
            "level": classification.level,
            "premise_scan_needed": classification.premise_scan_needed,
            "conflict_seeking": classification.conflict_seeking,
            "reasoning": classification.reasoning,
        },
    }
    if trace_collector:
        trace_collector.add_stage("classify", classify_data)

    if audit_mode:
        yield {
            "type": "audit_classify",
            "data": json.dumps(classify_data),
        }

    # Step 2: Premise check (if flagged by classifier)
    premise_flag = None
    premise_result = None
    if classification.premise_scan_needed:
        yield {"type": "status", "data": "Checking premise..."}
        t_premise = time.perf_counter()
        try:
            premise_result = await scan_premise(working_query, llm)
            if premise_result.has_premise:
                premise_result = await verify_premise(premise_result, effective_filter)
                if premise_result.correction:
                    premise_flag = {
                        "premise": premise_result.premise,
                        "correction": premise_result.correction,
                        "source_citation": premise_result.source_citation,
                    }
                    yield {"type": "premise_flag", "data": json.dumps(premise_flag)}
        except Exception as exc:
            logger.exception("Premise check failed")
            if audit_mode:
                yield {"type": "audit_error", "data": json.dumps({
                    "stage": "premise", "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-500:],
                })}
            # Continue without premise check

    if classification.premise_scan_needed and premise_result is not None:
        premise_elapsed = (time.perf_counter() - t_premise) * 1000
        premise_data = {
            "stage": "premise",
            "elapsed_ms": round(premise_elapsed, 1),
            "input": {"query": working_query},
            "output": {
                "has_premise": premise_result.has_premise,
                "premise": premise_result.premise,
                "verdict": "false_premise" if premise_result.correction else "no_premise_detected",
                "correction": premise_result.correction,
                "source_citation": premise_result.source_citation,
            },
        }
    else:
        premise_data = {
            "stage": "premise",
            "elapsed_ms": 0,
            "input": {"query": working_query},
            "output": {
                "has_premise": False,
                "premise": "",
                "verdict": "skipped",
            },
        }

    if trace_collector:
        trace_collector.add_stage("premise", premise_data)

    if audit_mode:
        yield {
            "type": "audit_premise",
            "data": json.dumps(premise_data),
        }

    tree_answer: str = ""   # populated in L3+ branch; used for reranking

    # Step 3: Retrieve
    all_results: list[RetrievalResult] = []
    if level in ("L1", "L2"):
        yield {"type": "status", "data": "Retrieving..."}
        t_ret = time.perf_counter()
        try:
            results, breakdown = await asyncio.to_thread(
                retrieve, working_query, effective_filter, return_breakdown=True
            )
        except Exception as exc:
            logger.exception("Retrieval failed")
            if audit_mode:
                yield {"type": "audit_error", "data": json.dumps({
                    "stage": "retrieve", "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-500:],
                })}
            results = []
            breakdown = {}
        retrieve_ms = (time.perf_counter() - t_ret) * 1000
        all_results = results
        if not audit_mode:
            # In audit mode the sidebar is driven by the post-rerank sources emit
            # at line 353. Emitting a preliminary list here would show a stale count
            # that shrinks once reranking completes.
            yield {"type": "sources", "data": json.dumps(_format_sources_event(results))}

        retrieve_data = {
            "stage": "retrieve",
            "elapsed_ms": round(retrieve_ms, 1),
            "input": {"query": working_query, "agency_filter": effective_filter},
            "output": {
                "total_results": len(results),
                "source_counts": {
                    "vector": sum(1 for r in results if "vector" in r.retrieval_sources),
                    "bm25": sum(1 for r in results if "bm25" in r.retrieval_sources),
                },
                "top_5": [
                    {
                        "citation": r.citation,
                        "score": round(r.score, 4),
                        "agency": r.agency,
                        "text_excerpt": r.text[:200],
                        "retrieval_sources": r.retrieval_sources,
                    }
                    for r in results[:5]
                ],
                "chunks": [
                    {
                        "citation": r.citation,
                        "score": round(r.score, 4),
                        "agency": r.agency,
                        "retrieval_sources": r.retrieval_sources,
                    }
                    for r in results
                ],
                "breakdown": breakdown,
            },
        }
        if trace_collector:
            trace_collector.add_stage("retrieve", retrieve_data)

        if audit_mode:
            yield {
                "type": "audit_retrieve",
                "data": json.dumps(retrieve_data),
            }
    else:
        # RT-RAG decomposition for L3+ queries
        yield {"type": "status", "data": "Decomposing into sub-queries..."}
        t_decomp = time.perf_counter()
        try:
            tree = await decompose_query(working_query, level, llm)
        except Exception as exc:
            logger.exception("Decomposition failed")
            if audit_mode:
                yield {"type": "audit_error", "data": json.dumps({
                    "stage": "decompose", "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-500:],
                })}
            # Fallback to L2
            level = "L2"
            tree = None
        decompose_ms = (time.perf_counter() - t_decomp) * 1000
        leaf_count = tree.leaf_count if tree else 0

        if tree is not None:
            decompose_data = {
                "stage": "decompose",
                "elapsed_ms": round(decompose_ms, 1),
                "input": {"query": working_query, "level": level},
                "output": {
                    "tree": _serialize_tree(tree),
                    "leaf_count": leaf_count,
                    "depth": _tree_depth(tree),
                },
            }
            if trace_collector:
                trace_collector.add_stage("decompose", decompose_data)

            if audit_mode:
                yield {
                    "type": "audit_decompose",
                    "data": json.dumps(decompose_data),
                }

            # solve_tree handles retrieval at each leaf
            yield {"type": "status", "data": f"Retrieving across {leaf_count} sub-queries..."}
            t_ret = time.perf_counter()
            try:
                tree_results, tree_answer, leaf_stats = await solve_tree(tree, effective_filter, llm)
            except Exception as exc:
                logger.exception("Tree solving failed")
                if audit_mode:
                    yield {"type": "audit_error", "data": json.dumps({
                        "stage": "retrieve", "error": str(exc),
                        "error_type": type(exc).__name__,
                        "traceback": traceback.format_exc()[-500:],
                    })}
                tree_results = []
                tree_answer = ""
                leaf_stats = {}
        else:
            # Fallback: treat as L2
            yield {"type": "status", "data": "Retrieving..."}
            t_ret = time.perf_counter()
            try:
                results, breakdown = await asyncio.to_thread(
                    retrieve, working_query, effective_filter, return_breakdown=True
                )
                tree_results = results
                tree_answer = ""
                leaf_stats = {}
            except Exception as exc:
                logger.exception("Fallback retrieval failed")
                if audit_mode:
                    yield {"type": "audit_error", "data": json.dumps({
                        "stage": "retrieve", "error": str(exc),
                        "error_type": type(exc).__name__,
                        "traceback": traceback.format_exc()[-500:],
                    })}
                tree_results = []
                tree_answer = ""
                leaf_stats = {}

        retrieve_ms = (time.perf_counter() - t_ret) * 1000
        # Deduplicate across leaves (keep highest score per chunk_id) and
        # sort globally by score descending so display order is correct.
        all_results = _dedup_and_sort(tree_results)
        # Aggregate sources event after all leaves solved. Suppressed in audit mode
        # (sidebar is driven by the post-rerank emit at line 353).
        if not audit_mode:
            yield {"type": "sources", "data": json.dumps(_format_sources_event(all_results))}

        per_leaf = leaf_stats  # already has chunk_count, methods, etc.
        retrieve_data_l3 = {
            "stage": "retrieve",
            "elapsed_ms": round(retrieve_ms, 1),
            "input": {"query": working_query, "agency_filter": effective_filter},
            "output": {
                "total_results": len(all_results),
                "source_counts": {
                    "vector": sum(1 for r in all_results if "vector" in r.retrieval_sources),
                    "bm25": sum(1 for r in all_results if "bm25" in r.retrieval_sources),
                },
                "top_5": [
                    {
                        "citation": r.citation,
                        "score": round(r.score, 4),
                        "agency": r.agency,
                        "text_excerpt": r.text[:200],
                        "retrieval_sources": r.retrieval_sources,
                    }
                    for r in all_results[:5]
                ],
                "per_leaf": per_leaf,
            },
        }
        if trace_collector:
            trace_collector.add_stage("retrieve", retrieve_data_l3)

        if audit_mode:
            yield {
                "type": "audit_retrieve",
                "data": json.dumps(retrieve_data_l3),
            }

    # Merge with cached chunks from prior turns (D-18: cached get small RRF boost)
    if session.chunk_cache:
        cached_results = list(session.chunk_cache.values())
        for cr in cached_results:
            if cr.chunk_id not in {r.chunk_id for r in all_results}:
                boosted = RetrievalResult(
                    chunk_id=cr.chunk_id,
                    text=cr.text,
                    score=cr.score * 0.8,  # slight decay for cached
                    citation=cr.citation,
                    section_title=cr.section_title,
                    agency=cr.agency,
                    authority_level=cr.authority_level,
                    document_type=cr.document_type,
                    retrieval_sources=["cache"],
                )
                all_results.append(boosted)

    # Apply synthesis budget and reranking:
    # L1/L2: query-embedding rerank (budget inside rerank_by_query) + graph expansion
    # L3+:   answer-embedding rerank (budget inside rerank_by_answer) + graph expansion
    if level in ("L1", "L2"):
        # Rerank against query embedding so best chunks rise to the top,
        # then inject up to 5 graph-adjacent authority chunks
        t_rerank_start = time.perf_counter()
        all_results, rerank_audit = await asyncio.to_thread(
            rerank_by_query, working_query, all_results, level, audit_mode=True
        )
        t_rerank_end = time.perf_counter()
        rerank_data = {
            "stage": "rerank",
            "elapsed_ms": round((t_rerank_end - t_rerank_start) * 1000, 1),
            **rerank_audit,
        }
        if trace_collector:
            trace_collector.add_stage("rerank", rerank_data)
        if audit_mode:
            yield {"type": "audit_rerank", "data": json.dumps(rerank_data)}

        # Phase 8 S10 (08-05): on-demand citation resolution before graph
        # expansion. Flag-gated, idempotent MERGE write-back, silent-
        # fallback — flag off is byte-for-byte legacy behaviour.
        if GRAPH_FEATURE_ONDEMAND_RESOLVER:
            await asyncio.to_thread(_run_on_demand_resolver, all_results)

        t_graph_start = time.perf_counter()
        all_results, graph_audit = await asyncio.to_thread(
            expand_by_graph_from_query, all_results, working_query, audit_mode=True
        )
        t_graph_end = time.perf_counter()
        graph_expand_data = {
            "stage": "graph_expand",
            "elapsed_ms": round((t_graph_end - t_graph_start) * 1000, 1),
            **graph_audit,
        }
        if trace_collector:
            trace_collector.add_stage("graph_expand", graph_expand_data)
        if audit_mode:
            yield {"type": "audit_graph_expand", "data": json.dumps(graph_expand_data)}
    elif tree_answer.strip():
        t_rerank_start = time.perf_counter()
        all_results, rerank_audit = await asyncio.to_thread(
            rerank_by_answer, tree_answer, all_results, level, audit_mode=True
        )
        t_rerank_end = time.perf_counter()
        rerank_data = {
            "stage": "rerank",
            "elapsed_ms": round((t_rerank_end - t_rerank_start) * 1000, 1),
            **rerank_audit,
        }
        if trace_collector:
            trace_collector.add_stage("rerank", rerank_data)
        if audit_mode:
            yield {"type": "audit_rerank", "data": json.dumps(rerank_data)}

        # Phase 8 (08-04) S3: multi-sub-question seed fusion for L3+.
        # Union per-leaf seeds and build a composite query vector from the
        # embeddings cached on the decomposer tree leaves — NO new embed
        # call (D-06 binding). fuse_seeds/graph_expander consume the cached
        # leaf.query_vec that solve_tree stashed via retrieve(return_query_vec=True).
        override_seeds: list[str] | None = None
        override_query_vec = None
        if GRAPH_FEATURE_SEED_FUSION and level in ("L3", "L4", "L5", "L6") and tree is not None:
            from src.graph.seed_fusion import SubQuestionResult, fuse_seeds

            sub_results: list[SubQuestionResult] = []
            for leaf in tree.leaves():
                seed_ids_for_leaf = [
                    r.chunk_id for r in leaf.retrieval_results[:GRAPH_EXPAND_SEEDS]
                ]
                sub_results.append(
                    SubQuestionResult(
                        sub_question=leaf.query,
                        seed_chunk_ids=seed_ids_for_leaf,
                        # Read cached vector; DO NOT embed here.
                        query_vec=leaf.query_vec,
                    )
                )
            override_seeds, override_query_vec = fuse_seeds(sub_results)

        # Phase 8 S10 (08-05): on-demand citation resolution before L3+
        # graph expansion. Flag-gated, idempotent MERGE write-back,
        # silent-fallback — flag off is byte-for-byte legacy behaviour.
        if GRAPH_FEATURE_ONDEMAND_RESOLVER:
            await asyncio.to_thread(_run_on_demand_resolver, all_results)

        t_graph_start = time.perf_counter()
        all_results, graph_audit = await asyncio.to_thread(
            expand_by_graph, all_results, tree_answer,
            audit_mode=True,
            override_seeds=override_seeds,
            override_query_vec=override_query_vec,
        )
        t_graph_end = time.perf_counter()
        graph_expand_data = {
            "stage": "graph_expand",
            "elapsed_ms": round((t_graph_end - t_graph_start) * 1000, 1),
            **graph_audit,
        }
        if trace_collector:
            trace_collector.add_stage("graph_expand", graph_expand_data)
        if audit_mode:
            yield {"type": "audit_graph_expand", "data": json.dumps(graph_expand_data)}
    else:
        # tree_answer empty (all leaves hit retrieval limit): fallback to score sort
        all_results.sort(key=lambda r: -r.score)
        all_results = all_results[:SYNTHESIS_TOP_K.get(level, RETRIEVAL_TOP_K)]

    # Step 3b: Conflict expansion (when classifier flagged conflict_seeking)
    if classification.conflict_seeking and CONFLICT_EXPAND_ENABLED:
        yield {"type": "status", "data": "Searching for cross-agency conflicts..."}
        scoring_text = tree_answer if tree_answer.strip() else working_query
        t_conflict_start = time.perf_counter()
        all_results, conflict_audit = await asyncio.to_thread(
            expand_conflicts, all_results, scoring_text, audit_mode=True
        )
        t_conflict_end = time.perf_counter()
        conflict_expand_data = {
            "stage": "conflict_expand",
            "elapsed_ms": round((t_conflict_end - t_conflict_start) * 1000, 1),
            **conflict_audit,
        }
        if trace_collector:
            trace_collector.add_stage("conflict_expand", conflict_expand_data)
        if audit_mode:
            yield {"type": "audit_conflict_expand", "data": json.dumps(conflict_expand_data)}

    # Phase 8 (08-04) S5: MMR-style diversity re-rank before the final
    # top-k / token-budget cut.  k=len(results) so this only re-orders —
    # downstream SYNTHESIS_TOP_K / enforce_token_budget handle truncation.
    if GRAPH_FEATURE_DIVERSITY and all_results:
        from src.graph.diverse_ranker import diverse_topk

        all_results = diverse_topk(all_results, k=len(all_results), lambda_=0.7)

    # Step 3c: Token budget gate — hard-cap context size before synthesis
    all_results, budget_report = enforce_token_budget(all_results, level=level)
    if trace_collector:
        trace_collector.add_stage("budget", {"stage": "budget_gate", **budget_report})
    if audit_mode:
        yield {
            "type": "audit_budget",
            "data": json.dumps({"stage": "budget_gate", **budget_report}),
        }

    # CRITICAL: align sidebar ordering with build_context()'s authority sort.
    # build_context() sorts by AUTHORITY_HIERARCHY then -score before assigning
    # source_num = 1..N. The sidebar uses source_num for its numbered manifest,
    # so the re-emitted `sources` event must match that order or the sidebar's
    # (i+1) badges drift away from build_context's assignment. Pre-sort
    # all_results here so:
    #   1. The re-emitted sources event matches build_context's order
    #   2. build_context's sort becomes a no-op (idempotent on sorted input)
    #   3. The cache stores results in synthesis-display order
    # (The LLM cites by `[{citation}]` regardless of order, so this is
    # purely about the sidebar's display numbering.)
    all_results.sort(
        key=lambda r: (AUTHORITY_HIERARCHY.get(r.authority_level, 99), -r.score)
    )

    # The earlier sources event fired before the synthesis budget/rerank step
    # mutated all_results. Re-emit now so the sidebar reflects exactly what the
    # synthesizer iterates over — LLM citation markers [1], [2], ... must align
    # with sidebar ordering for all query levels (L1/L2 cap, L3+ rerank+graph).
    yield {"type": "sources", "data": json.dumps(_format_sources_event(all_results))}

    # Cache results for this turn
    session_mgr.add_to_chunk_cache(sid, all_results)

    # Phase 8 S6 (08-06): extractive context composer.  Gated by
    # GRAPH_FEATURE_COMPOSER.  When on, replaces expansion chunks' text
    # with first+last sentence, drops section-level duplicates of seeds,
    # applies a greedy knapsack on score/cost, and produces a relational
    # preamble threaded into synthesize_answer's context block.  Flag-off
    # leaves `all_results` and the synthesiser's context assembly
    # byte-for-byte unchanged (D-17). D-01/D-08 binding: strictly
    # extractive, zero LLM/embedding calls in src/graph/context_composer.
    synthesis_preamble = ""
    if GRAPH_FEATURE_COMPOSER and all_results:
        try:
            from src.graph.context_composer import compose

            seeds = [
                r for r in all_results
                if "graph_expand" not in (r.retrieval_sources or [])
            ]
            expansions = [
                r for r in all_results
                if "graph_expand" in (r.retrieval_sources or [])
            ]
            composer_budget = max(
                1024,
                SYNTHESIS_CONTEXT_MAX_TOKENS - SYNTHESIS_OVERHEAD_TOKENS,
            )
            prompt_block = compose(
                seeds=seeds,
                expansions=expansions,
                paths=[],   # beam paths not threaded through pipeline yet
                prompt_budget=composer_budget,
            )
            synthesis_preamble = prompt_block.preamble or ""

            # Replace expansion chunks' text with the first+last-sentence
            # compression; drop expansions the composer did not include
            # (section-level duplicates + knapsack losers).  Seeds are
            # always kept -- the composer treats them as non-negotiable.
            included = set(prompt_block.included_chunk_ids)
            from src.graph.context_composer import _extract_first_last

            composed_results: list[RetrievalResult] = []
            for r in all_results:
                is_expansion = "graph_expand" in (r.retrieval_sources or [])
                if is_expansion:
                    if r.chunk_id not in included:
                        continue
                    new_text = _extract_first_last(r.text)
                    composed_results.append(
                        RetrievalResult(
                            chunk_id=r.chunk_id,
                            text=new_text,
                            score=r.score,
                            citation=r.citation,
                            section_title=r.section_title,
                            agency=r.agency,
                            authority_level=r.authority_level,
                            document_type=r.document_type,
                            retrieval_sources=r.retrieval_sources,
                            graph_context=r.graph_context,
                            citation_path=r.citation_path,
                        )
                    )
                else:
                    composed_results.append(r)
            all_results = composed_results
        except Exception as exc:
            # Silent-fallback -- a composer bug must never block synthesis.
            logger.debug("context_composer: silent fallback: %s", exc)
            synthesis_preamble = ""

    # Step 4: Synthesize
    yield {"type": "status", "data": "Synthesizing answer..."}

    _synthesis_ctx_data = {
        "stage": "synthesis_context",
        "reranking_method": (
            "query_embedding" if level in ("L1", "L2")
            else "answer_embedding" if tree_answer.strip()
            else "score_fallback"
        ),
        "graph_expanded_count": sum(
            1 for r in all_results if "graph_expand" in r.retrieval_sources
        ),
        "conflict_expanded_count": sum(
            1 for r in all_results if "conflict_expand" in r.retrieval_sources
        ),
        "budget_report": budget_report,
        "chunk_count": len(all_results),
        "total_tokens": sum(count_tokens_for_audit(r.text) for r in all_results),
        "chunks": [
            {
                "citation": r.citation,
                "agency": r.agency,
                "score": round(r.score, 4),
                "text_excerpt": r.text,
                "tokens": count_tokens_for_audit(r.text),
                "retrieval_sources": r.retrieval_sources,
                "chunk_id": r.chunk_id,
                "graph_context": r.graph_context,
            }
            for r in all_results
        ],
    }
    if trace_collector:
        trace_collector.add_stage("synthesis_context", _synthesis_ctx_data)
    if audit_mode:
        yield {
            "type": "audit_synthesis_context",
            "data": json.dumps(_synthesis_ctx_data),
        }

    answer_text_parts = []
    try:
        async for event in synthesize_answer(
            working_query,
            all_results,
            llm,
            session_context=session.turns,
            premise_flag=premise_flag,
            query_level=level,
            session_id=sid,
            audit_mode=audit_mode,
            context_preamble=synthesis_preamble,
        ):
            yield event
            if event["type"] == "token":
                answer_text_parts.append(event["data"])
            elif event["type"] == "audit_llm_io" and trace_collector:
                # Capture LLM I/O stage from synthesizer for always-on trace
                llm_io_data = event["data"] if isinstance(event["data"], dict) else json.loads(event["data"]) if isinstance(event["data"], str) else event["data"]
                trace_collector.add_stage("llm_io", llm_io_data)
    except Exception as exc:
        logger.exception("Synthesis failed")
        if audit_mode:
            yield {"type": "audit_error", "data": json.dumps({
                "stage": "synthesize", "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc()[-500:],
            })}
        # Emit fallback answer
        yield {"type": "token", "data": "An error occurred during answer synthesis. Please check the audit log for details."}

    # Record turn in session history
    full_answer = "".join(answer_text_parts)
    session_mgr.add_turn(sid, query, full_answer)

    # Emit session_id and done.
    # NOTE: "done" data must be non-empty — FastAPI's SSE encoder omits the
    # data: line for empty strings, causing the JS parser to never dispatch
    # the done event and leaving the UI stuck in "Synthesizing..." state.
    yield {"type": "session_id", "data": sid}
    yield {"type": "done", "data": "done"}


def _dedup_and_sort(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Deduplicate results by chunk_id (keep highest score) and sort descending.

    When multiple leaves in an L3+ decomposition tree return the same chunk,
    this keeps the copy with the highest RRF score and discards duplicates.
    Results are returned sorted by score descending so display order matches
    relevance.
    """
    best: dict[str, RetrievalResult] = {}
    for r in results:
        existing = best.get(r.chunk_id)
        if existing is None:
            best[r.chunk_id] = r
        else:
            # Merge retrieval_sources from both copies, keep higher score
            winner = r if r.score > existing.score else existing
            loser = existing if r.score > existing.score else r
            merged_sources = list(
                dict.fromkeys(winner.retrieval_sources + loser.retrieval_sources)
            )
            best[r.chunk_id] = RetrievalResult(
                chunk_id=winner.chunk_id,
                text=winner.text,
                score=winner.score,
                citation=winner.citation,
                section_title=winner.section_title,
                agency=winner.agency,
                authority_level=winner.authority_level,
                document_type=winner.document_type,
                retrieval_sources=merged_sources,
                graph_context=winner.graph_context or loser.graph_context,
                citation_path=winner.citation_path or loser.citation_path,
            )
    deduped = list(best.values())
    deduped.sort(key=lambda r: -r.score)
    return deduped


def _format_sources_event(results: list[RetrievalResult]) -> list[dict]:
    """Format retrieval results for the sources SSE event.

    Includes the full chunk text so the frontend can show a truncated
    preview by default and reveal the full text on expand.
    """
    return [
        {
            "chunk_id": r.chunk_id,
            "citation": r.citation,
            "agency": r.agency,
            "section_title": r.section_title,
            "score": round(r.score, 3),
            "text_excerpt": r.text,
            "authority_level": r.authority_level,
            "citation_path": {k: None if isinstance(v, float) and math.isnan(v) else v
                              for k, v in (r.citation_path or {}).items()},
            "retrieval_sources": r.retrieval_sources,
            "graph_context": r.graph_context,
        }
        for r in results
    ]
