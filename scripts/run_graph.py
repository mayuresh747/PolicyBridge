#!/usr/bin/env python
"""Build or update the Kuzu knowledge graph from LanceDB chunks.

Orchestrates the full Phase 2 pipeline per D-08: build citation index,
extract rule-based relationships, load chunk nodes and edges into Kuzu.

Usage:
    python scripts/run_graph.py --mode full         # Wipe + full rebuild
    python scripts/run_graph.py --mode incremental   # Retry unresolved + add new
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb

from src.config import DATA_DIR, KUZU_PATH, LLM_CACHE_PATH, LANCEDB_PATH, LANCEDB_TABLE_NAME
from src.graph.citation_index import build_citation_index
from src.graph.extractor import Relationship, extract_all_relationships, extract_hierarchy
from src.graph.llm_extractor import extract_relationships_llm
from src.graph.kuzu_writer import KuzuWriter

logger = logging.getLogger(__name__)

UNRESOLVED_PATH = DATA_DIR / "unresolved_citations.json"


def run_full(use_regex: bool = False) -> None:
    """Wipe and rebuild the entire Kuzu knowledge graph from all LanceDB chunks.

    Steps:
    1. Connect to LanceDB, open chunks table
    2. Build citation index
    3. Extract cross-chunk relationships (LLM or regex)
    4. Destroy existing Kuzu DB (full rebuild)
    5. Create schema, load nodes, load edges
    6. Write unresolved citations to data/unresolved_citations.json
    7. Print summary

    Args:
        use_regex: If True, use legacy regex extraction instead of LLM (gpt-4.1-mini).
    """
    start = time.time()
    logger.info("Starting full graph build...")

    # 1. Connect to LanceDB
    db = lancedb.connect(str(LANCEDB_PATH))
    table = db.open_table(LANCEDB_TABLE_NAME)
    logger.info("Connected to LanceDB at %s", LANCEDB_PATH)

    # 2. Build citation index
    citation_index, chapter_index = build_citation_index(table)
    logger.info(
        "Citation index: %d entries, Chapter index: %d prefixes",
        len(citation_index),
        len(chapter_index),
    )

    # 3. Get chunks DataFrame
    chunks_df = table.to_pandas()
    logger.info("Loaded %d chunks from LanceDB", len(chunks_df))

    # 4. Extract cross-chunk relationships
    if use_regex:
        logger.info("Using regex extraction (--use-regex flag)")
        relationships, unresolved = extract_all_relationships(
            chunks_df, citation_index, chapter_index
        )
    else:
        logger.info("Using LLM extraction (gpt-4.1-mini)...")
        relationships, unresolved = extract_relationships_llm(
            chunks_df, citation_index, chapter_index,
            cache_path=LLM_CACHE_PATH,
        )

    # 4b. Build hierarchy (Agency → Document → Chunk)
    agency_nodes, doc_nodes, agency_doc_edges, doc_chunk_edges = extract_hierarchy(chunks_df)
    logger.info(
        "Hierarchy: %d agencies, %d documents, %d agency→doc edges, %d doc→chunk edges",
        len(agency_nodes),
        len(doc_nodes),
        len(agency_doc_edges),
        len(doc_chunk_edges),
    )

    # Count cross-chunk relationship types
    type_counts: dict[str, int] = {}
    for rel in relationships:
        type_counts[rel.rel_type] = type_counts.get(rel.rel_type, 0) + 1
    logger.info("Extracted %d cross-chunk relationships:", len(relationships))
    for rt, cnt in sorted(type_counts.items()):
        logger.info("  %s: %d", rt, cnt)
    logger.info("Unresolved citations: %d", len(unresolved))

    # 5. Destroy existing Kuzu DB for full rebuild
    writer = KuzuWriter()
    writer.destroy()
    logger.info("Destroyed existing Kuzu DB (full rebuild)")

    # 6. Create fresh writer, schema, load
    writer = KuzuWriter()
    writer.create_schema()

    # Load nodes: agency first, then documents, then chunks (no FK constraint
    # in Kuzu, but logical ordering aids debugging)
    writer.load_agency_nodes(agency_nodes)
    writer.load_document_nodes(doc_nodes)
    node_count = writer.load_nodes(chunks_df)

    # Load hierarchy edges (must come after all nodes are loaded)
    writer.load_hierarchy_edges(agency_doc_edges, doc_chunk_edges)

    # Load cross-chunk edges
    edge_counts = writer.load_edges(relationships)

    # 7. Write unresolved citations per D-06
    UNRESOLVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UNRESOLVED_PATH, "w") as f:
        json.dump(unresolved, f, indent=2)
    logger.info(
        "Wrote %d unresolved citations to %s", len(unresolved), UNRESOLVED_PATH
    )

    # CONFLICTS_WITH detection deferred to future phase
    logger.info("CONFLICTS_WITH detection is deferred to a future phase.")

    # 8. Final summary
    counts = writer.get_edge_counts()
    writer.close()

    elapsed = time.time() - start

    print("\n" + "=" * 60)
    print("  GRAPH BUILD SUMMARY")
    print("=" * 60)
    print(f"  Agency nodes:       {len(agency_nodes)}")
    print(f"  Document nodes:     {len(doc_nodes)}")
    print(f"  Chunk nodes:        {node_count}")
    for rel_type, count in sorted(counts.items()):
        if count > 0:
            print(f"  {rel_type:<22} {count:>6} edges")
    print(f"  Unresolved citations: {len(unresolved)}")
    print(f"  Time elapsed:       {elapsed:.1f}s")
    print("=" * 60)


def run_incremental() -> None:
    """Add new chunks and retry unresolved citations against updated index.

    Steps:
    1. Connect to LanceDB, build fresh citation index
    2. Load existing unresolved citations from JSON
    3. Re-check each against updated index
    4. For newly resolved: create edges via merge_edge
    5. Write updated unresolved list back
    """
    start = time.time()
    logger.info("Starting incremental graph update...")

    # 1. Connect to LanceDB
    db = lancedb.connect(str(LANCEDB_PATH))
    table = db.open_table(LANCEDB_TABLE_NAME)

    # 2. Build fresh citation index
    citation_index, chapter_index = build_citation_index(table)
    logger.info(
        "Citation index: %d entries, Chapter index: %d prefixes",
        len(citation_index),
        len(chapter_index),
    )

    # 3. Load existing unresolved citations
    if UNRESOLVED_PATH.exists():
        with open(UNRESOLVED_PATH) as f:
            unresolved = json.load(f)
        logger.info("Loaded %d unresolved citations from %s", len(unresolved), UNRESOLVED_PATH)
    else:
        unresolved = []
        logger.info("No unresolved citations file found, nothing to retry")

    # 4. Open Kuzu writer (existing DB)
    writer = KuzuWriter()

    # 5. Re-check unresolved citations per D-07
    from src.graph.citation_index import normalize_citation, resolve_citation

    still_unresolved = []
    resolved_count = 0

    for entry in unresolved:
        raw_citation = entry["raw_citation"]
        target_id = resolve_citation(raw_citation, citation_index, chapter_index)

        if target_id:
            # Resolved! Create edge via MERGE
            writer.merge_edge(
                source_id=entry["source_chunk_id"],
                target_id=target_id,
                rel_type=entry["relationship_type"],
                confidence=1.0,
            )
            resolved_count += 1
            logger.debug(
                "Resolved: %s -> %s (%s)",
                entry["source_chunk_id"],
                target_id,
                entry["relationship_type"],
            )
        else:
            still_unresolved.append(entry)

    # 6. Write updated unresolved list
    UNRESOLVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UNRESOLVED_PATH, "w") as f:
        json.dump(still_unresolved, f, indent=2)

    writer.close()

    elapsed = time.time() - start

    logger.info(
        "Resolved %d previously unresolved citations, %d remaining",
        resolved_count,
        len(still_unresolved),
    )

    print("\n" + "=" * 60)
    print("INCREMENTAL UPDATE COMPLETE")
    print("=" * 60)
    print(f"Resolved: {resolved_count}")
    print(f"Still unresolved: {len(still_unresolved)}")
    print(f"Elapsed: {elapsed:.1f}s")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build/update Kuzu knowledge graph from LanceDB chunks"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        required=True,
        help="full = wipe + rebuild; incremental = retry unresolved + add new",
    )
    parser.add_argument(
        "--use-regex",
        action="store_true",
        help="Use legacy regex extraction instead of LLM (gpt-4.1-mini)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Delete the LLM extraction cache before running (forces full re-extraction)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.clear_cache and LLM_CACHE_PATH.exists():
        LLM_CACHE_PATH.unlink()
        logger.info("Cleared LLM extraction cache: %s", LLM_CACHE_PATH)

    if args.mode == "full":
        run_full(use_regex=args.use_regex)
    else:
        run_incremental()


if __name__ == "__main__":
    main()
