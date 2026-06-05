"""Stage 3: Parallel per-section extraction using Claude Haiku + tool_use."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Type

from pydantic import BaseModel

from . import config, llm
from .classifier import pages_for
from .ingest import CIMDocument
from .models import (
    CIMSummary,
    CompanyOverview,
    CustomersAndExit,
    DealCriteria,
    DealHeader,
    DealOverview,
    Financials,
    HighlightsAndRisks,
    IndustryCompetitors,
    ManagementBio,
    OtherConsiderations,
    ProductOffering,
    SectionMap,
    SourcesAndUses,
    SponsorOverview,
    SponsorValueCreation,
)
from .prompts.sections import SECTION_PROMPTS

log = logging.getLogger(__name__)


class _ManagementBios(BaseModel):
    bios: list[ManagementBio] = []


SECTION_SCHEMAS: dict[str, Type[BaseModel]] = {
    "deal_header": DealHeader,
    "deal_overview": DealOverview,
    "deal_criteria": DealCriteria,
    "company_overview": CompanyOverview,
    "sources_and_uses": SourcesAndUses,
    "highlights_and_risks": HighlightsAndRisks,
    "sponsor_value_creation": SponsorValueCreation,
    "product_offering": ProductOffering,
    "industry_competitors": IndustryCompetitors,
    "customers_and_exit": CustomersAndExit,
    "other_considerations": OtherConsiderations,
    "sponsor_overview": SponsorOverview,
    "management_bios": _ManagementBios,
    "financials": Financials,
}


def _section_user_text(
    doc: CIMDocument,
    section_map: SectionMap,
    key: str,
    deal_name: str,
    sponsor_name: str,
) -> str:
    pages = pages_for(section_map, key)
    if not pages:
        # Fall back to whole-doc snippet (truncated) so we always produce something
        text = doc.all_text(char_budget=config.SECTION_TEXT_CHAR_BUDGET)
    else:
        text = doc.text_by_pages(pages, char_budget=config.SECTION_TEXT_CHAR_BUDGET)
    return (
        f"Deal name: {deal_name}\nSeller / Sponsor (if known): {sponsor_name}\n\n"
        f"=== RELEVANT CIM EXCERPTS ===\n{text}\n=== END EXCERPTS ==="
    )


def _extract_one(
    key: str,
    doc: CIMDocument,
    section_map: SectionMap,
    deal_name: str,
    sponsor_name: str,
) -> tuple[str, BaseModel | None, Exception | None]:
    schema = SECTION_SCHEMAS[key]
    section_prompt = SECTION_PROMPTS[key]
    tone = llm.load_tone()
    system = f"{tone}\n\n--- TASK ---\n{section_prompt}"
    user = _section_user_text(doc, section_map, key, deal_name, sponsor_name)
    try:
        obj = llm.call_structured(
            model=config.CLAUDE_MODEL_HAIKU,
            system=system,
            user=user,
            schema=schema,
            max_tokens=3000,
            temperature=0.2,
        )
        return key, obj, None
    except Exception as e:
        log.exception("extractor %s failed: %s", key, e)
        return key, None, e


def extract_all(
    doc: CIMDocument,
    section_map: SectionMap,
    deal_name: str,
    sponsor_name: str,
    on_progress=None,
) -> CIMSummary:
    summary = CIMSummary()
    # Pre-fill header with user inputs
    summary.header.project_name = deal_name
    summary.header.sponsor_name = sponsor_name

    keys = list(SECTION_SCHEMAS.keys())
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_extract_one, k, doc, section_map, deal_name, sponsor_name): k
            for k in keys
        }
        for fut in as_completed(futures):
            key, obj, err = fut.result()
            done += 1
            if on_progress:
                on_progress(key, done, len(keys), err)
            if obj is None:
                continue
            if key == "management_bios":
                summary.management_bios = obj.bios  # type: ignore[attr-defined]
            elif key == "deal_header":
                summary.header = obj  # type: ignore[assignment]
            else:
                setattr(summary, key, obj)

    # If extractor left header empty, keep user inputs
    if not summary.header.project_name:
        summary.header.project_name = deal_name
    if not summary.header.sponsor_name:
        summary.header.sponsor_name = sponsor_name
    return summary
