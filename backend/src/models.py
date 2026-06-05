"""Pydantic models for CIMSummarizer (PRD §5.3)."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class YesNo(str, Enum):
    YES = "Yes"
    NO = "No"
    UNCLEAR = "Unclear"


class DealHeader(BaseModel):
    project_name: str = ""
    sponsor_name: str = ""
    date: str = ""


class DealOverview(BaseModel):
    bullets: list[str] = Field(default_factory=list)


class DealCriterion(BaseModel):
    criterion: str
    result: YesNo = YesNo.UNCLEAR
    note: str = ""


class DealCriteria(BaseModel):
    target_industry: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="In target industry (B2B services, industrial, niche manufacturing)")
    )
    ltm_ebitda_above_3m: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="LTM EBITDA >= $3M")
    )
    hq_north_america: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="HQ in North America")
    )
    control_acquisition: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="Control acquisition available")
    )
    sponsor_angle: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="Sponsor angle / clear value-creation thesis")
    )
    seller_rollover: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="Seller rollover / continued involvement")
    )
    hits_return_expectations: DealCriterion = Field(
        default_factory=lambda: DealCriterion(criterion="Hits return expectations (>=2.5x MoM / >=20% IRR)")
    )


class CompanyOverview(BaseModel):
    narrative: str = ""
    revenue: Optional[str] = None
    ebitda: Optional[str] = None


class SourcesUsesItem(BaseModel):
    item: str
    amount_m: Optional[float] = None
    multiple: Optional[str] = None


class SourcesAndUses(BaseModel):
    sources: list[SourcesUsesItem] = Field(default_factory=list)
    uses: list[SourcesUsesItem] = Field(default_factory=list)
    sources_total: Optional[float] = None
    uses_total: Optional[float] = None
    ltm_ebitda: Optional[float] = None
    balanced: bool = False
    note: str = ""


class InvestmentPoint(BaseModel):
    bullet: str


class HighlightsAndRisks(BaseModel):
    highlights: list[InvestmentPoint] = Field(default_factory=list)
    risks: list[InvestmentPoint] = Field(default_factory=list)


class SponsorValueCreation(BaseModel):
    bullets: list[str] = Field(default_factory=list)


class ProductOffering(BaseModel):
    description: Optional[str] = ""
    image_page_numbers: list[int] = Field(default_factory=list)
    # absolute file paths (server-side) to selected images
    image_paths: list[str] = Field(default_factory=list)


class IndustryCompetitors(BaseModel):
    industry_overview: str = ""
    competitors: str = ""


class CustomersAndExit(BaseModel):
    key_customers: str = ""
    exit_returns: str = ""


class OtherConsiderations(BaseModel):
    content: str = ""


class SponsorOverview(BaseModel):
    content: str = ""


class ManagementBio(BaseModel):
    name: str
    title: str = ""
    summary: str = ""


class FinancialRow(BaseModel):
    metric: str
    values: dict[str, Optional[float]] = Field(default_factory=dict)
    cagr: Optional[str] = None
    cagr_forecasted: Optional[str] = None


class Financials(BaseModel):
    rows: list[FinancialRow] = Field(default_factory=list)
    has_projections: bool = False


class CIMSummary(BaseModel):
    header: DealHeader = Field(default_factory=DealHeader)
    deal_overview: DealOverview = Field(default_factory=DealOverview)
    deal_criteria: DealCriteria = Field(default_factory=DealCriteria)
    company_overview: CompanyOverview = Field(default_factory=CompanyOverview)
    sources_and_uses: SourcesAndUses = Field(default_factory=SourcesAndUses)
    highlights_and_risks: HighlightsAndRisks = Field(default_factory=HighlightsAndRisks)
    sponsor_value_creation: SponsorValueCreation = Field(default_factory=SponsorValueCreation)
    product_offering: ProductOffering = Field(default_factory=ProductOffering)
    industry_competitors: IndustryCompetitors = Field(default_factory=IndustryCompetitors)
    customers_and_exit: CustomersAndExit = Field(default_factory=CustomersAndExit)
    other_considerations: OtherConsiderations = Field(default_factory=OtherConsiderations)
    sponsor_overview: SponsorOverview = Field(default_factory=SponsorOverview)
    management_bios: list[ManagementBio] = Field(default_factory=list)
    financials: Financials = Field(default_factory=Financials)


# Section-id mapping used by the classifier
SECTION_ID_TO_KEY: dict[int, str] = {
    1: "deal_header",
    2: "deal_overview",
    3: "deal_criteria",
    4: "company_overview",
    5: "sources_and_uses",
    6: "highlights_and_risks",  # both highlights + risks
    7: "highlights_and_risks",
    8: "sponsor_value_creation",
    9: "product_offering",
    10: "industry_competitors",
    11: "financials",
    12: "customers_and_exit",
    13: "sponsor_overview",
    14: "management_bios",
}


class PageRange(BaseModel):
    start: int
    end: int
    confidence: float = 0.5


class SectionMap(BaseModel):
    """page ranges per output-section key."""
    sections: dict[str, list[PageRange]] = Field(default_factory=dict)
    total_pages: int = 0


# Job state
class JobStage(str, Enum):
    QUEUED = "queued"
    INGEST = "ingest"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SYNTHESIZE = "synthesize"
    ASSEMBLE = "assemble"
    DONE = "done"
    ERROR = "error"


class StageEvent(BaseModel):
    stage: JobStage
    message: str = ""
    progress: float = 0.0  # 0..1
    ts: float


class JobState(BaseModel):
    id: str
    filename: str
    deal_name: str
    sponsor_name: str
    stage: JobStage = JobStage.QUEUED
    error: Optional[str] = None
    summary: Optional[CIMSummary] = None
    page_count: int = 0
    created_at: float
    updated_at: float
    events: list[StageEvent] = Field(default_factory=list)
