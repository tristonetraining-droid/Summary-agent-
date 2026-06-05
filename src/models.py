"""Pydantic data models for BriefForge.

These schemas are the contract between pipeline stages and are also used as
structured-output (tool use) shapes for Claude, which enforces grounding by
construction: the model can only fill fields we define.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SectionSummary(BaseModel):
    """Summary of a single section of the source report (MAP phase output)."""

    section_title: str = Field(..., description="Title or label of the section.")
    summary: str = Field(..., description="Concise, grounded summary of the section.")
    key_figures: list[str] = Field(
        default_factory=list,
        description="Specific figures/claims that appear verbatim in the section.",
    )
    source_pages: str = Field(
        default="",
        description="Approximate page range for this section, e.g. '12-18'.",
    )


class ExecutiveSummary(BaseModel):
    """Final one-page executive summary (REDUCE phase output)."""

    report_title: str
    source: str = Field(..., description="e.g. 'J.P. Morgan Wealth Management'.")
    report_date: str
    page_count: int
    headline_takeaway: str = Field(
        ..., description="The single most important point of the report."
    )
    key_findings: list[str] = Field(
        ..., description="3-5 grounded bullet points."
    )
    market_implications: str = Field(..., description="2-3 sentences.")
    risks: list[str] = Field(..., description="2-3 risk bullets.")
    bottom_line: str = Field(..., description="1-2 sentence recommendation.")
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Anything the model was unsure about or could not verify.",
    )


class AuditRecord(BaseModel):
    """Immutable record of a single pipeline run for SOC2/ISO audit trails."""

    run_id: str
    source_url: str
    pdf_hash: str
    timestamp: str
    model: str
    page_count: int
    output_path: str
    status: str
