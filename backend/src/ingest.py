"""Stage 1: PDF ingest — text, tables, page rasters."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber

from . import config

log = logging.getLogger(__name__)


@dataclass
class PageContent:
    page_num: int  # 1-indexed
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    has_images: bool = False


@dataclass
class CIMDocument:
    pdf_path: Path
    pages: list[PageContent]
    raster_dir: Optional[Path] = None  # dir containing page-{n}.png

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def text_by_pages(self, page_nums: list[int], char_budget: int | None = None) -> str:
        chunks: list[str] = []
        total = 0
        for p in sorted(set(page_nums)):
            if 1 <= p <= self.page_count:
                t = self.pages[p - 1].text or ""
                chunk = f"\n\n[Page {p}]\n{t.strip()}"
                if char_budget and total + len(chunk) > char_budget:
                    chunks.append(chunk[: max(0, char_budget - total)])
                    break
                chunks.append(chunk)
                total += len(chunk)
        return "".join(chunks).strip()

    def all_text(self, char_budget: int | None = None) -> str:
        return self.text_by_pages(list(range(1, self.page_count + 1)), char_budget=char_budget)


def extract_pdf(pdf_path: Path) -> CIMDocument:
    """Extract text + tables from every page using pdfplumber."""
    pdf_path = Path(pdf_path).resolve()
    pages: list[PageContent] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                log.warning("text extract failed page %s: %s", i, e)
                text = ""
            tables: list[list[list[str]]] = []
            try:
                raw_tables = page.extract_tables() or []
                for t in raw_tables:
                    cleaned = [[(c or "").strip() for c in row] for row in t if any((c or "").strip() for c in row)]
                    if cleaned:
                        tables.append(cleaned)
            except Exception as e:
                log.warning("table extract failed page %s: %s", i, e)
            has_images = bool(getattr(page, "images", []))
            pages.append(
                PageContent(
                    page_num=i,
                    text=text,
                    tables=tables,
                    width=float(page.width),
                    height=float(page.height),
                    has_images=has_images,
                )
            )
    return CIMDocument(pdf_path=pdf_path, pages=pages)


def rasterize_pages(
    pdf_path: Path,
    out_dir: Path,
    pages: Optional[list[int]] = None,
    dpi: int = config.DEFAULT_PAGE_DPI,
) -> dict[int, Path]:
    """Rasterize selected pages to PNGs. Returns {page_num: png_path}.

    Uses pdf2image if available (requires poppler); falls back to PyMuPDF/None gracefully.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[int, Path] = {}
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as e:
        log.warning("pdf2image unavailable: %s — skipping rasterization", e)
        return result

    poppler_path = config.POPPLER_PATH or None

    if pages:
        for p in sorted(set(pages)):
            try:
                imgs = convert_from_path(
                    str(pdf_path), dpi=dpi, first_page=p, last_page=p,
                    poppler_path=poppler_path,
                )
                if imgs:
                    out = out_dir / f"page-{p}.png"
                    imgs[0].save(out, "PNG")
                    result[p] = out
            except Exception as e:
                log.warning("rasterize page %s failed: %s", p, e)
    else:
        try:
            imgs = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
            for idx, img in enumerate(imgs, start=1):
                out = out_dir / f"page-{idx}.png"
                img.save(out, "PNG")
                result[idx] = out
        except Exception as e:
            log.warning("rasterize all failed: %s", e)
    return result


def detect_scanned(doc: CIMDocument) -> bool:
    """Heuristic: scanned PDFs have near-zero extractable text."""
    if not doc.pages:
        return False
    total_chars = sum(len(p.text or "") for p in doc.pages)
    return total_chars / max(1, doc.page_count) < 80
