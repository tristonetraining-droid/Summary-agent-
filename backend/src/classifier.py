"""Stage 2: Map CIM pages to the output sections."""
from __future__ import annotations

import logging
from typing import Any

from . import config, llm
from .ingest import CIMDocument
from .models import PageRange, SectionMap

log = logging.getLogger(__name__)

# Section IDs used in the classifier prompt -> internal output keys
ID_TO_KEY: dict[int, str] = {
    1: "deal_header",
    2: "deal_overview",
    3: "deal_criteria",
    4: "company_overview",
    5: "sources_and_uses",
    6: "highlights",
    7: "risks",
    8: "sponsor_value_creation",
    9: "product_offering",
    10: "industry_competitors",
    11: "financials",
    12: "customers_and_exit",
    13: "sponsor_overview",
    14: "management_bios",
}


def _build_index(doc: CIMDocument, max_pages: int) -> str:
    chunks: list[str] = []
    for p in doc.pages[:max_pages]:
        snippet = (p.text or "")[: config.CLASSIFIER_PAGE_TEXT_CHARS]
        chunks.append(f"--- Page {p.page_num} ---\n{snippet.strip()}")
    return "\n\n".join(chunks)


def classify_sections(doc: CIMDocument) -> SectionMap:
    if doc.page_count == 0:
        return SectionMap(sections={}, total_pages=0)

    system = llm.load_prompt("classifier.txt")
    max_pages = min(doc.page_count, config.MAX_PAGES_FOR_CLASSIFIER)
    user = (
        f"The CIM has {doc.page_count} pages total. Here are the first {max_pages} pages (text per page, truncated):\n\n"
        + _build_index(doc, max_pages)
        + "\n\nReturn JSON only."
    )
    try:
        data: Any = llm.call_json(
            model=config.CLAUDE_MODEL_SONNET,
            system=system,
            user=user,
            max_tokens=2000,
            temperature=0.1,
        )
    except Exception as e:
        log.exception("classifier failed: %s — falling back to whole-document map", e)
        return _fallback_map(doc)

    sections: dict[str, list[PageRange]] = {}
    for row in data.get("assignments", []):
        sid = int(row.get("section_id", 0))
        pages = row.get("pages") or []
        if sid not in ID_TO_KEY or len(pages) < 1:
            continue
        start = int(pages[0])
        end = int(pages[-1]) if len(pages) > 1 else start
        conf = float(row.get("confidence", 0.6))
        key = ID_TO_KEY[sid]
        sections.setdefault(key, []).append(PageRange(start=start, end=end, confidence=conf))

    # Merge highlights+risks into highlights_and_risks
    h = sections.pop("highlights", [])
    r = sections.pop("risks", [])
    if h or r:
        sections["highlights_and_risks"] = h + r

    return SectionMap(sections=sections, total_pages=doc.page_count)


def _fallback_map(doc: CIMDocument) -> SectionMap:
    """If classifier fails, give every section the whole document."""
    n = doc.page_count
    full = [PageRange(start=1, end=n, confidence=0.3)]
    keys = [
        "deal_header", "deal_overview", "deal_criteria", "company_overview",
        "sources_and_uses", "highlights_and_risks", "sponsor_value_creation",
        "product_offering", "industry_competitors", "customers_and_exit",
        "other_considerations", "sponsor_overview", "management_bios", "financials",
    ]
    return SectionMap(sections={k: list(full) for k in keys}, total_pages=n)


def pages_for(section_map: SectionMap, key: str) -> list[int]:
    pages: set[int] = set()
    for pr in section_map.sections.get(key, []):
        for p in range(pr.start, pr.end + 1):
            pages.add(p)
    return sorted(pages)
