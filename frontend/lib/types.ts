// Mirror of backend Pydantic CIMSummary
export type YesNo = "Yes" | "No" | "Unclear";

export interface DealHeader { project_name: string; sponsor_name: string; date: string; }
export interface DealOverview { bullets: string[]; }

export interface DealCriterion { criterion: string; result: YesNo; note: string; }
export interface DealCriteria {
  target_industry: DealCriterion;
  ltm_ebitda_above_3m: DealCriterion;
  hq_north_america: DealCriterion;
  control_acquisition: DealCriterion;
  sponsor_angle: DealCriterion;
  seller_rollover: DealCriterion;
  hits_return_expectations: DealCriterion;
}

export interface CompanyOverview { narrative: string; revenue: string | null; ebitda: string | null; }
export interface SourcesUsesItem { item: string; amount_m: number | null; multiple: string | null; }
export interface SourcesAndUses {
  sources: SourcesUsesItem[];
  uses: SourcesUsesItem[];
  sources_total: number | null;
  uses_total: number | null;
  ltm_ebitda: number | null;
  balanced: boolean;
  note: string;
}
export interface InvestmentPoint { bullet: string; }
export interface HighlightsAndRisks { highlights: InvestmentPoint[]; risks: InvestmentPoint[]; }
export interface SponsorValueCreation { bullets: string[]; }
export interface ProductOffering {
  description: string | null;
  image_page_numbers: number[];
  image_paths: string[];
}
export interface IndustryCompetitors { industry_overview: string; competitors: string; }
export interface CustomersAndExit { key_customers: string; exit_returns: string; }
export interface OtherConsiderations { content: string; }
export interface SponsorOverview { content: string; }
export interface ManagementBio { name: string; title: string; summary: string; }
export interface FinancialRow { metric: string; values: Record<string, number | null>; cagr: string | null; cagr_forecasted: string | null; }
export interface Financials { rows: FinancialRow[]; has_projections: boolean; }

export interface CIMSummary {
  header: DealHeader;
  deal_overview: DealOverview;
  deal_criteria: DealCriteria;
  company_overview: CompanyOverview;
  sources_and_uses: SourcesAndUses;
  highlights_and_risks: HighlightsAndRisks;
  sponsor_value_creation: SponsorValueCreation;
  product_offering: ProductOffering;
  industry_competitors: IndustryCompetitors;
  customers_and_exit: CustomersAndExit;
  other_considerations: OtherConsiderations;
  sponsor_overview: SponsorOverview;
  management_bios: ManagementBio[];
  financials: Financials;
}

export interface SavedSummaryMeta {
  id: string;
  job_id: string;
  deal_name: string;
  sponsor_name: string;
  saved_at: string;
}

export interface SavedSummary extends SavedSummaryMeta {
  summary: CIMSummary;
}

export type JobStage =
  | "queued" | "ingest" | "classify" | "extract" | "synthesize" | "assemble" | "done" | "error";

export interface StageEvent { stage: JobStage; message: string; progress: number; ts: number; }

export interface JobState {
  id: string;
  filename: string;
  deal_name: string;
  sponsor_name: string;
  stage: JobStage;
  error: string | null;
  summary: CIMSummary | null;
  page_count: number;
  created_at: number;
  updated_at: number;
  events: StageEvent[];
}
