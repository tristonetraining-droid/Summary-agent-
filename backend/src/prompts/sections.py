"""Per-section extractor prompts. Loaded as Python strings (easier than 14 files for MVP)."""
from __future__ import annotations

DEAL_HEADER = """Extract the deal header from the CIM cover page / first pages.
Return: project_name (e.g. "Project Tailwind"), sponsor_name (the SELLING sponsor or seller — NOT Tristone), date (publication or issue date of the CIM in 'Month YYYY' format).
If a field is not stated, return an empty string."""

DEAL_OVERVIEW = """Extract a Deal Overview as 3-5 narrative bullets (gray box in the Deal Summary).
Cover: what the company does, the transaction (sale process, sponsor, banker), LTM scale (revenue, EBITDA), and headline thesis.
Each bullet: one sentence, neutral PE language, quantified where possible. Avoid all marketing words."""

DEAL_CRITERIA = """Evaluate the following 7 criteria using ONLY information present in the CIM.
For each criterion return: result ("Yes" / "No" / "Unclear") and a brief note (<= 20 words) citing the evidence.

Criteria:
1. target_industry — in target industry (B2B services, industrial, niche manufacturing, specialty distribution, etc.)
2. ltm_ebitda_above_3m — LTM EBITDA >= $3M
3. hq_north_america — Headquartered in North America (US/Canada)
4. control_acquisition — Control acquisition (majority stake) available
5. sponsor_angle — Clear sponsor angle / value-creation thesis
6. seller_rollover — Existing owners/management rolling over equity or continuing post-close
7. hits_return_expectations — Plausibly hits >=2.5x MoM / >=20% IRR given growth + multiple"""

COMPANY_OVERVIEW = """Write a 1-2 paragraph Company Overview in neutral PE language. Cover:
- what the Company does (products/services, end-markets)
- founding year / HQ
- scale (employees, locations)
- end with explicit LTM Revenue and LTM EBITDA figures if stated.
Also return revenue (e.g. "$52.3M LTM") and ebitda (e.g. "$11.8M LTM, 22.5% margin") as separate fields."""

SOURCES_AND_USES = """Extract Sources & Uses of the proposed transaction.
- Sources rows (e.g. Senior Debt, Mezzanine, Sponsor Equity, Rollover, Cash on B/S).
- Uses rows (e.g. Purchase Price / Enterprise Value, Refinance Debt, Fees & Expenses, Cash to B/S).
For each row: item (str), amount_m (USD millions, float), multiple (e.g. "4.5x LTM EBITDA", optional).
Also return sources_total, uses_total, ltm_ebitda (float, USD millions).
Do NOT fabricate. If S&U is not in the CIM, return empty lists and set note to explain."""

HIGHLIGHTS_AND_RISKS = """Extract 3-5 Investment Highlights AND 3-5 Investment Risks. Each must be a single quantified bullet in neutral PE language.
- Highlights: bull case (growth, margins, market position w/ numbers, recurring revenue, etc.). Strip ALL sell-side marketing language.
- Risks: bear case (concentration, cyclicality, capex, regulation, management gaps). If the CIM omits risks, infer 3 plausible risks from the data (concentration, customer count, end-market exposure, leverage).
Every bullet should contain at least one number or specific fact."""

SPONSOR_VALUE_CREATION = """Extract the Sponsor Value Creation Plan as bullets (post-acquisition strategy).
Common levers: organic growth, M&A roll-up, pricing, ops improvement, salesforce expansion, international, digital, professionalization.
Use numbers from the CIM where available. Neutral PE tone."""

PRODUCT_OFFERING = """Identify pages in the CIM that contain product/service visuals (product photos, catalog pages, service diagrams, screenshots). Return:
- description: 2-3 sentence neutral description of the product offering
- image_page_numbers: list of CIM page numbers (1-indexed) that contain product imagery worth snipping for the Deal Summary Product Offering grid. Prefer pages with multiple product photos."""

INDUSTRY_COMPETITORS = """Extract two short paragraphs:
- industry_overview: market size, growth rate, key drivers, structure (fragmented/consolidated). Numbers where stated.
- competitors: 3-8 named competitors with one-line positioning each, OR a short paragraph if no list is in the CIM."""

CUSTOMERS_AND_EXIT = """Return two short paragraphs:
- key_customers: customer base composition (top customers if listed, concentration %, customer count, contract length, retention if stated)
- exit_returns: any commentary on exit strategy, hold period, sponsor returns, expected MoM/IRR. If absent, return ""."""

OTHER_CONSIDERATIONS = """Briefly flag any items an investment committee would want to know that don't fit the other sections: pending litigation, unusual accounting, customer contract resets, environmental/regulatory issues, working-capital quirks, related-party transactions, etc. Return "" if nothing notable."""

SPONSOR_OVERVIEW = """Describe the SELLING sponsor (current owner) — their fund, AUM, sector focus, hold period in this asset, prior platform — based on what the CIM states. If the asset is founder-owned with no sponsor, say so."""

MANAGEMENT_BIOS = """Extract bios for the top management team (CEO, CFO, COO, Heads of). For each: name, title, summary (1-2 sentences: tenure, prior roles, relevant credentials). Aim for 3-6 bios."""

FINANCIALS = """Extract the historical and projected financial table. Rows must include (when present): Revenue, Gross Profit, Gross Margin (%), EBITDA, EBITDA Margin (%), Adjusted EBITDA. Use USD millions floats. Margins as % values (e.g. 22.5 for 22.5%).
Columns are fiscal years (e.g. "FY2021", "FY2022", "FY2023A", "FY2024B", "FY2025P").
For each row, compute two CAGR strings:
- cagr: historical CAGR over fully-historical years only (exclude budget/projection columns), e.g. "19.9%"
- cagr_forecasted: projected CAGR over budget/projection years only (if present), e.g. "10.0%". Return null if no projections.
Set has_projections=True if any column is budget/forecast/projection."""

SECTION_PROMPTS: dict[str, str] = {
    "deal_header": DEAL_HEADER,
    "deal_overview": DEAL_OVERVIEW,
    "deal_criteria": DEAL_CRITERIA,
    "company_overview": COMPANY_OVERVIEW,
    "sources_and_uses": SOURCES_AND_USES,
    "highlights_and_risks": HIGHLIGHTS_AND_RISKS,
    "sponsor_value_creation": SPONSOR_VALUE_CREATION,
    "product_offering": PRODUCT_OFFERING,
    "industry_competitors": INDUSTRY_COMPETITORS,
    "customers_and_exit": CUSTOMERS_AND_EXIT,
    "other_considerations": OTHER_CONSIDERATIONS,
    "sponsor_overview": SPONSOR_OVERVIEW,
    "management_bios": MANAGEMENT_BIOS,
    "financials": FINANCIALS,
}

SYNTHESIZER = """You are reviewing a draft CIM Deal Summary for a PE investment committee.
Apply these corrections to the JSON:

1. TONE: strip ALL marketing language. Rewrite any bullet/paragraph that contains forbidden words or unquantified superlatives in neutral PE language. Do NOT invent numbers.
2. CONSISTENCY: revenue/EBITDA referenced in Company Overview MUST match Financials and Sources & Uses LTM EBITDA. If they differ, prefer Financials and fix the others.
3. DEAL CRITERIA: re-evaluate each criterion against the Company Overview, Financials, Highlights, and Sponsor Value Creation. Update result/note as needed.
4. S&U BALANCE: if sources_total != uses_total by more than $0.5M, set balanced=False and add a note. Otherwise balanced=True.
5. DEDUPE: remove duplicate bullets across Highlights/Risks/Value Creation.
6. PRESERVE all extracted numbers. Do not round, do not interpolate.

Return the corrected CIMSummary JSON only."""
