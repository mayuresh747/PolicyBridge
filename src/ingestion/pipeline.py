"""Ingestion pipeline for the Seattle Regulatory RAG system.

Orchestrates PDF scanning, parsing, chunking, embedding, and storage across all
8 agency folders using multiprocessing.Pool with maxtasksperchild=1 for memory
isolation (mitigates Docling's memory leak on repeated conversions).

Pipeline flow: scan PDFs -> filter via manifest -> parse+chunk (multiprocessing)
-> embed with OpenAI -> store in LanceDB -> update manifest.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from src.chunkers.base import ChunkData, get_chunker, normalize_text
from src.config import (
    AGENCY_FOLDERS,
    DOCUMENTS_ROOT,
    EMBED_BATCH_SIZE,
    FAILURES_PATH,
    LANCEDB_PATH,
    MANIFEST_PATH,
    MULTIPROCESSING_WORKERS,
)
from src.ingestion.parser import parse_pdf


def process_pdf(args: tuple) -> dict:
    """Parse and chunk a single PDF. Runs in a worker process.

    Must be a top-level function for pickling by multiprocessing.

    Args:
        args: Tuple of (pdf_path: str, agency: str) or
            (pdf_path: str, agency: str, skip_ocr: bool).

    Returns:
        Dict with keys:
        - status: "success", "failed", or "skipped"
        - chunks: List[ChunkData] (on success)
        - path: str (original PDF path)
        - agency: str
        - reason: str (on skipped, e.g. "ocr_required")
        - error: str (on failure)
        - traceback: str (on failure)
    """
    pdf_path, agency, skip_ocr = (*args, False)[:3]

    try:
        result = parse_pdf(pdf_path, skip_ocr=skip_ocr)

        if result is None:
            return {
                "status": "skipped",
                "path": pdf_path,
                "agency": agency,
                "reason": "ocr_required",
            }

        # Detect image artifacts before normalization
        from src.chunkers.base import _IMAGE_ARTIFACT_RE
        has_images = bool(_IMAGE_ARTIFACT_RE.search(result.text))

        # Normalize text before chunking (strip artifacts, whitespace, special chars)
        clean_text = normalize_text(result.text)

        metadata = {
            "filename": Path(pdf_path).name,
            "agency": agency,
            "is_scanned": result.is_scanned,
            "ocr_confidence": result.ocr_confidence,
        }

        chunker = get_chunker(agency)
        chunks = chunker.chunk(clean_text, result.tables, metadata)

        # Assign sequential chunk_index and propagate document-level fields
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.has_images = has_images
            chunk.is_scanned = result.is_scanned
            if result.ocr_confidence is not None:
                chunk.ocr_confidence = result.ocr_confidence

        return {
            "status": "success",
            "chunks": chunks,
            "path": pdf_path,
            "agency": agency,
        }
    except Exception as e:
        print(f"WARNING: Failed to parse {pdf_path}: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "path": pdf_path,
            "agency": agency,
        }


def scan_agency_pdfs(agency: str) -> List[Path]:
    """Discover all PDFs in an agency's document folder.

    Uses Path.rglob for recursive discovery, which handles nested
    subdirectory structures like WAC/RCW Title_N/ folders.

    Args:
        agency: One of the 8 agency keys from AGENCY_FOLDERS.

    Returns:
        Sorted list of Path objects pointing to PDF files.

    Raises:
        FileNotFoundError: If the agency folder does not exist.
        ValueError: If the agency name is not recognized.
    """
    if agency not in AGENCY_FOLDERS:
        raise ValueError(
            f"Unknown agency: '{agency}'. "
            f"Valid agencies: {sorted(AGENCY_FOLDERS.keys())}"
        )

    folder_name = AGENCY_FOLDERS[agency]
    agency_path = DOCUMENTS_ROOT / folder_name

    if not agency_path.exists():
        raise FileNotFoundError(
            f"Agency folder does not exist: {agency_path}"
        )

    pdfs = sorted(agency_path.rglob("*.pdf"))
    return pdfs


def run_ingestion(
    agencies: Optional[List[str]] = None,
    workers: int = MULTIPROCESSING_WORKERS,
    resume_failed: bool = False,
) -> Dict:
    """Run the full ingestion pipeline across agency folders.

    Scans for PDFs, filters already-processed documents via the manifest,
    parses and chunks using multiprocessing.Pool with maxtasksperchild=1,
    embeds with OpenAI, stores in LanceDB, and tracks results in the manifest.

    Args:
        agencies: List of agency names to process. If None, processes all.
        workers: Number of multiprocessing workers (default from config).
        resume_failed: If True, re-attempts previously failed documents.

    Returns:
        Summary dict with per-agency chunk counts, failure list, timing,
        metadata completeness, and embedding cost.
    """
    from src.embeddings.openai_embedder import OpenAIEmbedder, embed_and_store
    from src.storage.lancedb_writer import LanceDBWriter
    from src.storage.manifest import FailureLog, IngestionManifest

    if agencies is None:
        agencies = list(AGENCY_FOLDERS.keys())

    # Initialize components
    writer = LanceDBWriter(LANCEDB_PATH)
    writer.create_table()
    manifest = IngestionManifest(MANIFEST_PATH)
    failure_log = FailureLog(FAILURES_PATH)
    embedder = OpenAIEmbedder()

    summary: Dict = {
        "chunks_per_agency": {},
        "failure_list": [],
        "metadata_completeness_per_agency": {},
        "processing_time": {},
        "embedding_cost": {},
        "total_chunks": 0,
        "total_failures": 0,
        "total_time_seconds": 0.0,
    }

    total_start = time.time()
    total_chunk_count = 0

    for agency in agencies:
        agency_start = time.time()
        agency_chunks_count = 0
        agency_total_fields = 0
        agency_complete_fields = 0

        try:
            pdfs = scan_agency_pdfs(agency)
        except (FileNotFoundError, ValueError) as e:
            print(f"WARNING: Skipping agency '{agency}': {e}")
            continue

        # Filter via manifest
        pdf_paths = [str(p) for p in pdfs]
        unprocessed = manifest.get_unprocessed(pdf_paths, resume_failed=resume_failed)

        if not unprocessed:
            print(f"  {agency}: All documents already processed, skipping.")
            continue

        tasks = [(path, agency) for path in unprocessed]
        chunk_buffer: List[ChunkData] = []
        buffer_threshold = EMBED_BATCH_SIZE * 10  # 1000 chunks

        with multiprocessing.Pool(
            processes=workers, maxtasksperchild=1
        ) as pool:
            desc = f"Agency: {agency}"
            with tqdm(
                total=len(tasks), desc=desc, unit="doc"
            ) as pbar:
                for result in pool.imap_unordered(process_pdf, tasks):
                    path = result["path"]

                    if result["status"] == "success":
                        chunks = result["chunks"]
                        chunk_buffer.extend(chunks)
                        agency_chunks_count += len(chunks)

                        # Track metadata completeness
                        for chunk in chunks:
                            agency_total_fields += 4
                            if chunk.agency:
                                agency_complete_fields += 1
                            if chunk.section_title:
                                agency_complete_fields += 1
                            if chunk.authority_level:
                                agency_complete_fields += 1
                            if chunk.citation:
                                agency_complete_fields += 1

                        # Update manifest
                        manifest.mark_complete(path, len(chunks))
                        manifest.save()

                        # Flush buffer when it reaches threshold
                        if len(chunk_buffer) >= buffer_threshold:
                            asyncio.run(
                                embed_and_store(chunk_buffer, embedder, writer)
                            )
                            chunk_buffer.clear()

                    else:
                        # Failure
                        manifest.mark_failed(
                            path, result["error"], result["traceback"]
                        )
                        failure_log.log_failure(
                            pdf_path=path,
                            error=result["error"],
                            stack_trace=result["traceback"],
                            agency=agency,
                        )
                        manifest.save()

                        summary["failure_list"].append({
                            "path": path,
                            "agency": agency,
                            "error_type": type(
                                Exception(result["error"])
                            ).__name__,
                            "error": result["error"],
                        })

                        print(
                            f"  WARNING: Failed {Path(path).name}: "
                            f"{result['error']}"
                        )

                    pbar.set_postfix(
                        agency=agency,
                        chunks=agency_chunks_count,
                    )
                    pbar.update(1)

        # Flush remaining chunks for this agency
        if chunk_buffer:
            asyncio.run(embed_and_store(chunk_buffer, embedder, writer))
            chunk_buffer.clear()

        agency_elapsed = time.time() - agency_start
        total_chunk_count += agency_chunks_count

        summary["chunks_per_agency"][agency] = agency_chunks_count
        summary["processing_time"][agency] = round(agency_elapsed, 2)
        summary["metadata_completeness_per_agency"][agency] = round(
            (agency_complete_fields / agency_total_fields * 100)
            if agency_total_fields > 0
            else 0.0,
            1,
        )

    total_elapsed = time.time() - total_start
    summary["total_chunks"] = total_chunk_count
    summary["total_failures"] = len(summary["failure_list"])
    summary["total_time_seconds"] = round(total_elapsed, 2)
    summary["embedding_cost"] = embedder.get_cost_summary()

    return summary


def print_summary(summary: Dict) -> None:
    """Format and print the end-of-run ingestion summary.

    Displays per-agency chunk counts, failure list, metadata completeness,
    processing time breakdown, and estimated embedding cost.

    Args:
        summary: Summary dict returned by run_ingestion().
    """
    print("\n" + "=" * 70)
    print("  INGESTION SUMMARY")
    print("=" * 70)

    # Per-agency chunk counts
    chunks_per_agency = summary.get("chunks_per_agency", {})
    if chunks_per_agency:
        print("\n  Chunks per agency:")
        print(f"  {'Agency':<25} {'Chunks':>10} {'Meta %':>10} {'Time (s)':>12}")
        print("  " + "-" * 57)
        for agency, count in chunks_per_agency.items():
            meta_pct = summary.get("metadata_completeness_per_agency", {}).get(
                agency, 0.0
            )
            proc_time = summary.get("processing_time", {}).get(agency, 0.0)
            print(f"  {agency:<25} {count:>10,} {meta_pct:>9.1f}% {proc_time:>12.1f}")
        print("  " + "-" * 57)
        print(
            f"  {'TOTAL':<25} {summary.get('total_chunks', 0):>10,}"
            f" {'':>10} {summary.get('total_time_seconds', 0):>12.1f}"
        )

    # Failure list
    failure_list = summary.get("failure_list", [])
    if failure_list:
        print(f"\n  Failures ({len(failure_list)}):")
        for f in failure_list:
            print(f"    - [{f['agency']}] {Path(f['path']).name}: {f['error']}")
    else:
        print("\n  No failures.")

    # Embedding cost
    cost = summary.get("embedding_cost", {})
    if cost:
        print(f"\n  Embedding cost:")
        print(f"    Tokens used:  {cost.get('total_tokens_used', 0):,}")
        print(f"    API calls:    {cost.get('total_api_calls', 0):,}")
        print(f"    Est. cost:    ${cost.get('estimated_cost_usd', 0):.4f}")

    print(f"\n  Total time: {summary.get('total_time_seconds', 0):.1f}s")
    print("=" * 70 + "\n")
