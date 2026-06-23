"""Docling-based PDF parser for the Seattle Regulatory RAG ingestion pipeline.

Wraps the Docling DocumentConverter with configuration optimized for regulatory
PDFs: TableFormer ACCURATE mode for complex tables, integrated OCR for scanned
page auto-detection, and per-document converter instances to prevent memory leaks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    OcrMacOptions,
    PdfPipelineOptions,
    TableFormerMode,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a single PDF document.

    Attributes:
        text: Full document content as Markdown via export_to_markdown().
        tables: Each table exported as a Markdown string.
        is_scanned: True if any page required OCR processing.
        ocr_confidence: Average OCR confidence if scanned, None otherwise.
        page_count: Number of pages in the document.
    """

    text: str
    tables: List[str] = field(default_factory=list)
    is_scanned: bool = False
    ocr_confidence: Optional[float] = None
    page_count: int = 0


def create_converter() -> DocumentConverter:
    """Create a fresh DocumentConverter configured for regulatory PDFs.

    Configuration:
    - TableFormer in ACCURATE mode for complex tables (merged cells,
      multi-level headers in SPU dimensional standards, SMC fee schedules).
    - OCR enabled with auto-detection of scanned/image-only pages.
    - Unnecessary enrichments disabled for performance.

    Returns:
        A configured DocumentConverter instance.
    """
    pipeline_options = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=True,
    )
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    return converter


def parse_pdf(pdf_path: Union[str, Path], skip_ocr: bool = False) -> Optional[ParseResult]:
    """Parse a single PDF document using Docling.

    Creates a fresh DocumentConverter per invocation to prevent memory leaks
    (Docling Issue #2209: 13GB accumulation on repeated conversions when
    reusing the same converter instance).

    Args:
        pdf_path: Path to the PDF file to parse.
        skip_ocr: If True, returns None for documents that would trigger OCR
            fallback (text density < 50 chars/page) instead of retrying with
            forced OCR.

    Returns:
        ParseResult with extracted text, tables, OCR status, and page count.
        None if skip_ocr=True and the document has low text density.

    Raises:
        Exception: Re-raised with the PDF path included in the error message.
    """
    pdf_path = Path(pdf_path)

    try:
        # Create fresh converter per document (memory leak mitigation)
        converter = create_converter()

        result = converter.convert(str(pdf_path))
        doc = result.document

        # Export full document text as Markdown
        text = doc.export_to_markdown()

        # Extract tables as Markdown strings
        tables: List[str] = []
        for table in doc.tables:
            try:
                df = table.export_to_dataframe(doc=doc)
                tables.append(df.to_markdown())
            except Exception as table_err:
                logger.warning(
                    "Failed to export table from %s: %s", pdf_path, table_err
                )

        # Detect OCR usage by checking page-level metadata
        is_scanned = False
        ocr_confidence: Optional[float] = None
        page_count = 0

        # Check pages for OCR indicators
        if hasattr(doc, "pages") and doc.pages:
            page_count = len(doc.pages)
            ocr_confidences: List[float] = []

            for page in doc.pages.values():
                if hasattr(page, "predictions"):
                    predictions = page.predictions
                    if hasattr(predictions, "ocr") and predictions.ocr:
                        is_scanned = True
                        if hasattr(predictions.ocr, "confidence"):
                            ocr_confidences.append(predictions.ocr.confidence)

            if ocr_confidences:
                ocr_confidence = sum(ocr_confidences) / len(ocr_confidences)

        # Fallback: if extraction is suspiciously sparse (hybrid PDF with minimal
        # embedded text but image content), retry with forced full-page OCR.
        # Threshold: < 50 chars/page covers clear failures (25-04: 7 chars/page)
        # while safely ignoring sparse-but-valid docs (normal minimum: ~200 chars/page).
        if page_count > 0 and len(text) / page_count < 50:
            if skip_ocr:
                logger.info(
                    "Skipping '%s' — low text density (%d chars, %d pages, %.1f chars/page) "
                    "and skip_ocr=True",
                    pdf_path, len(text), page_count, len(text) / page_count,
                )
                return None
            logger.warning(
                "Low text density in '%s' (%d chars, %d pages, %.1f chars/page) — "
                "retrying with forced full-page OCR",
                pdf_path, len(text), page_count, len(text) / page_count,
            )
            forced_options = PdfPipelineOptions(do_table_structure=True, do_ocr=True)
            forced_options.table_structure_options.mode = TableFormerMode.ACCURATE
            forced_options.ocr_options = OcrMacOptions(force_full_page_ocr=True)
            forced_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=forced_options)
                }
            )
            forced_result = forced_converter.convert(str(pdf_path))
            text = forced_result.document.export_to_markdown()
            is_scanned = True  # Treat as scanned since we needed forced OCR

        return ParseResult(
            text=text,
            tables=tables,
            is_scanned=is_scanned,
            ocr_confidence=ocr_confidence,
            page_count=page_count,
        )

    except Exception as e:
        raise type(e)(f"Failed to parse PDF '{pdf_path}': {e}") from e
