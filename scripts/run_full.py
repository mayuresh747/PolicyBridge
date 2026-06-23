"""Full corpus ingestion script for the Seattle Regulatory RAG system.

Runs the complete parse-chunk-embed-store pipeline across all (or selected)
agency folders. Supports resumable operation via the ingestion manifest,
optional re-processing of failed documents, and post-ingestion index creation.

Must be run AFTER scripts/run_sample.py validation has been reviewed and approved.
"""

import argparse
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.config import AGENCY_FOLDERS, LANCEDB_PATH
from src.ingestion.pipeline import print_summary, run_ingestion
from src.storage.lancedb_writer import LanceDBWriter


def main():
    """Run full corpus ingestion with CLI options."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Seattle Regulatory RAG — Full Corpus Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_full.py                    # All agencies\n"
            "  python scripts/run_full.py --agencies WAC,RCW # Specific agencies\n"
            "  python scripts/run_full.py --resume-failed    # Retry failed docs\n"
            "  python scripts/run_full.py --workers 8        # More parallelism\n"
            "  python scripts/run_full.py --skip-indexing    # Skip index creation\n"
        ),
    )
    parser.add_argument(
        "--agencies",
        type=str,
        default=None,
        help="Comma-separated list of agency names to process (default: all)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of multiprocessing workers (default: 4)",
    )
    parser.add_argument(
        "--resume-failed",
        action="store_true",
        help="Re-attempt previously failed documents",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip vector and FTS index creation after ingestion",
    )

    args = parser.parse_args()

    # Parse and validate agencies
    agencies = None
    if args.agencies:
        agencies = [a.strip() for a in args.agencies.split(",")]
        valid = set(AGENCY_FOLDERS.keys())
        invalid = [a for a in agencies if a not in valid]
        if invalid:
            print(f"ERROR: Unknown agencies: {invalid}")
            print(f"Valid agencies: {sorted(valid)}")
            sys.exit(1)

    # Banner
    start_time = time.time()
    print("=" * 70)
    print("  Seattle Regulatory RAG — Full Corpus Ingestion")
    print("=" * 70)
    if agencies:
        print(f"  Agencies: {', '.join(agencies)}")
    else:
        print(f"  Agencies: ALL ({len(AGENCY_FOLDERS)})")
    print(f"  Workers: {args.workers}")
    print(f"  Resume failed: {args.resume_failed}")
    print(f"  Skip indexing: {args.skip_indexing}")
    print("=" * 70)
    print()

    print("Starting full corpus ingestion...")

    # Run ingestion
    summary = run_ingestion(
        agencies=agencies,
        workers=args.workers,
        resume_failed=args.resume_failed,
    )

    # Print summary
    print_summary(summary)

    # Create indexes unless skipped
    if not args.skip_indexing:
        total_chunks = summary.get("total_chunks", 0)
        if total_chunks > 0:
            writer = LanceDBWriter(LANCEDB_PATH)
            writer.create_table()

            print("Creating vector index...")
            writer.create_vector_index()

            print("Creating BM25 FTS index...")
            writer.create_fts_index()

            print("Indexes created.")
        else:
            print("No chunks ingested — skipping index creation.")
    else:
        print("Index creation skipped (--skip-indexing).")

    # Final message
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print(f"  Ingestion complete.")
    print(f"  Total chunks: {summary.get('total_chunks', 0):,}")
    print(f"  Total failures: {summary.get('total_failures', 0)}")
    print(f"  Total time: {elapsed:.1f}s ({elapsed / 60:.1f}m)")
    print("=" * 70)


if __name__ == "__main__":
    main()
