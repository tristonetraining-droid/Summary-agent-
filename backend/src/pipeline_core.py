"""End-to-end CIM → CIMSummary pipeline (callable from CLI or service)."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from . import config
from .assembler import assemble
from .classifier import classify_sections, pages_for
from .extractors import extract_all
from .ingest import detect_scanned, extract_pdf, rasterize_pages
from .models import CIMSummary, JobStage
from .synthesizer import synthesize

log = logging.getLogger(__name__)

ProgressCB = Callable[[JobStage, str, float], None]


def run_pipeline(
    *,
    pdf_path: Path,
    job_dir: Path,
    deal_name: str,
    sponsor_name: str,
    on_progress: Optional[ProgressCB] = None,
) -> tuple[CIMSummary, Path, list[int]]:
    """Run all 5 stages. Returns (summary, docx_path, rasterized_pages)."""
    def emit(stage: JobStage, msg: str = "", prog: float = 0.0) -> None:
        log.info("[%s] %s (%.0f%%)", stage.value, msg, prog * 100)
        if on_progress:
            on_progress(stage, msg, prog)

    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    raster_dir = job_dir / "pages"
    raster_dir.mkdir(exist_ok=True)

    # Stage 1: Ingest
    emit(JobStage.INGEST, "Reading PDF…", 0.05)
    doc = extract_pdf(pdf_path)
    if detect_scanned(doc):
        emit(JobStage.INGEST, "Warning: low text density (possibly scanned PDF).", 0.1)
    emit(JobStage.INGEST, f"Parsed {doc.page_count} pages.", 0.15)

    # Stage 2: Classify
    emit(JobStage.CLASSIFY, "Mapping CIM → 11 sections…", 0.2)
    section_map = classify_sections(doc)
    emit(JobStage.CLASSIFY, f"Mapped {len(section_map.sections)} sections.", 0.3)

    # Rasterize product offering pages (and a sample of first pages) for UI
    product_pages = pages_for(section_map, "product_offering")[:24]
    sample_pages = list(range(1, min(doc.page_count, 8) + 1))
    rasterize_target = sorted(set(product_pages + sample_pages))
    rasterized = rasterize_pages(pdf_path, raster_dir, pages=rasterize_target)
    emit(JobStage.CLASSIFY, f"Rasterized {len(rasterized)} preview pages.", 0.35)

    # Stage 3: Extract (parallel)
    extracted_done = {"n": 0}

    def on_section(key: str, done: int, total: int, err: Exception | None) -> None:
        extracted_done["n"] = done
        emit(JobStage.EXTRACT, f"{key} ({done}/{total})", 0.35 + 0.4 * (done / total))

    summary = extract_all(doc, section_map, deal_name, sponsor_name, on_progress=on_section)

    # Attach product page numbers for UI image picker
    if not summary.product_offering.image_page_numbers and product_pages:
        summary.product_offering.image_page_numbers = product_pages

    # Stage 4: Synthesize
    emit(JobStage.SYNTHESIZE, "Tone + consistency pass…", 0.8)
    summary = synthesize(summary)

    # Stage 5: Assemble
    emit(JobStage.ASSEMBLE, "Building DOCX…", 0.9)
    safe = "".join(c for c in deal_name if c.isalnum() or c in ("-", "_")) or "Deal"
    docx_path = job_dir / f"CIM_Summary_{safe}.docx"
    assemble(summary, docx_path)

    emit(JobStage.DONE, "Complete.", 1.0)
    return summary, docx_path, sorted(rasterized.keys())
