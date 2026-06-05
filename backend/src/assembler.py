"""Stage 5: Assemble final DOCX.

Strategy: if a Tristone template exists at config.TEMPLATE_PATH with placeholder
tokens (e.g. {{DEAL_OVERVIEW}}), populate it; otherwise build a self-contained
4-page document programmatically that mirrors the template layout (navy sidebar,
color-coded boxes, green confidential footer).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsmap, qn
from docx.shared import Cm, Inches, Pt, RGBColor
from lxml import etree

from . import config
from .models import CIMSummary

log = logging.getLogger(__name__)


# Tristone palette
NAVY = RGBColor(0x0E, 0x2A, 0x47)
GRAY_BOX = "EFEFEF"
GREEN_BOX = "E2EFDA"
BLUE_BOX = "DDEBF7"
GREEN_FOOTER = "548235"
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def assemble(summary: CIMSummary, out_path: Path, template_path: Optional[Path] = None) -> Path:
    template_path = template_path or config.TEMPLATE_PATH
    if template_path and Path(template_path).exists():
        try:
            return _fill_template(summary, Path(template_path), out_path)
        except Exception as e:
            log.warning("template fill failed (%s) — falling back to generated layout", e)
    return _build_from_scratch(summary, out_path)


# ----- template-based fill (placeholder tokens) -----

PLACEHOLDERS = {
    "{{DEAL_NAME}}": lambda s: s.header.project_name,
    "{{SPONSOR_NAME}}": lambda s: s.header.sponsor_name,
    "{{DATE}}": lambda s: s.header.date,
    "{{DEAL_OVERVIEW}}": lambda s: "\n".join(f"• {b}" for b in s.deal_overview.bullets),
    "{{COMPANY_OVERVIEW}}": lambda s: s.company_overview.narrative,
    "{{REVENUE}}": lambda s: s.company_overview.revenue or "",
    "{{EBITDA}}": lambda s: s.company_overview.ebitda or "",
    "{{HIGHLIGHTS}}": lambda s: "\n".join(f"• {p.bullet}" for p in s.highlights_and_risks.highlights),
    "{{RISKS}}": lambda s: "\n".join(f"• {p.bullet}" for p in s.highlights_and_risks.risks),
    "{{VALUE_CREATION}}": lambda s: "\n".join(f"• {b}" for b in s.sponsor_value_creation.bullets),
    "{{INDUSTRY}}": lambda s: s.industry_competitors.industry_overview,
    "{{COMPETITORS}}": lambda s: s.industry_competitors.competitors,
    "{{KEY_CUSTOMERS}}": lambda s: s.customers_and_exit.key_customers,
    "{{EXIT_RETURNS}}": lambda s: s.customers_and_exit.exit_returns,
    "{{OTHER}}": lambda s: s.other_considerations.content,
    "{{SPONSOR_OVERVIEW}}": lambda s: s.sponsor_overview.content,
    "{{MANAGEMENT}}": lambda s: "\n".join(
        f"{b.name} — {b.title}: {b.summary}" for b in s.management_bios
    ),
    "{{PRODUCT_DESC}}": lambda s: s.product_offering.description or "",
}


def _fill_template(summary: CIMSummary, template_path: Path, out_path: Path) -> Path:
    doc = Document(str(template_path))
    for para in doc.paragraphs:
        _replace_in_paragraph(para, summary)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _replace_in_paragraph(para, summary)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def _replace_in_paragraph(para, summary: CIMSummary) -> None:
    if "{{" not in para.text:
        return
    full = para.text
    for token, fn in PLACEHOLDERS.items():
        if token in full:
            full = full.replace(token, str(fn(summary)))
    # Replace runs
    for r in para.runs:
        r.text = ""
    if para.runs:
        para.runs[0].text = full
    else:
        para.add_run(full)


# ----- programmatic 4-page layout (mirrors template visually) -----

def _shade(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = etree.SubElement(tc_pr, qn("w:shd"))
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)


def _set_cell_borders(cell, color: str = "BFBFBF", sz: int = 4) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = etree.SubElement(tc_pr, qn("w:tcBorders"))
    for edge in ("top", "left", "bottom", "right"):
        b = etree.SubElement(borders, qn(f"w:{edge}"))
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(sz))
        b.set(qn("w:color"), color)


def _heading(cell, text: str, color: RGBColor = NAVY) -> None:
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = color
    run.font.underline = True


def _add_bullets(cell, bullets: list[str], color: RGBColor = RGBColor(0x22, 0x22, 0x22)) -> None:
    first = True
    for b in bullets:
        if not b:
            continue
        if first:
            p = cell.add_paragraph()
            first = False
        else:
            p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(f"• {b}")
        run.font.size = Pt(9)
        run.font.color.rgb = color


def _add_text(cell, text: str, size: int = 9) -> None:
    if not text:
        return
    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.font.size = Pt(size)


def _box_table(doc, heading_text: str, body_fn, fill: str, width: float = 17.5) -> None:
    t = doc.add_table(rows=2, cols=1)
    t.autofit = False
    t.columns[0].width = Cm(width)
    head_cell = t.rows[0].cells[0]
    body_cell = t.rows[1].cells[0]
    head_cell.width = Cm(width)
    body_cell.width = Cm(width)
    _shade(head_cell, fill)
    _shade(body_cell, fill)
    _set_cell_borders(head_cell, color="D0D0D0")
    _set_cell_borders(body_cell, color="D0D0D0")
    _heading(head_cell, heading_text)
    body_fn(body_cell)


def _build_from_scratch(summary: CIMSummary, out_path: Path) -> Path:
    doc = Document()

    # Page setup: narrow margins, A4
    for section in doc.sections:
        section.top_margin = Cm(1.0)
        section.bottom_margin = Cm(1.0)
        section.left_margin = Cm(1.0)
        section.right_margin = Cm(1.0)

    # === Page 1 ===
    # Header
    h = doc.add_paragraph()
    h.paragraph_format.space_after = Pt(0)
    run = h.add_run(summary.header.project_name or "Project")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = NAVY
    sub = doc.add_paragraph()
    sr = sub.add_run(
        f"Sponsor: {summary.header.sponsor_name}    |    {summary.header.date}".strip()
    )
    sr.font.size = Pt(10)
    sr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Deal Overview (gray)
    _box_table(
        doc, "Deal Overview",
        lambda c: _add_bullets(c, summary.deal_overview.bullets),
        GRAY_BOX,
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # Deal Criteria (green) — 2-column bullet layout
    crit = summary.deal_criteria
    dc_table = doc.add_table(rows=2, cols=2)
    dc_table.autofit = False
    dc_table.columns[0].width = Cm(8.75)
    dc_table.columns[1].width = Cm(8.75)
    dc_head = dc_table.rows[0].cells[0]
    dc_head.merge(dc_table.rows[0].cells[1])
    _shade(dc_head, GREEN_BOX)
    _set_cell_borders(dc_head, "D0D0D0")
    _heading(dc_head, "Deal Criteria")
    dc_left = dc_table.rows[1].cells[0]
    dc_right = dc_table.rows[1].cells[1]
    _shade(dc_left, GREEN_BOX)
    _shade(dc_right, GREEN_BOX)
    _set_cell_borders(dc_left, "D0D0D0")
    _set_cell_borders(dc_right, "D0D0D0")
    for c in [crit.target_industry, crit.ltm_ebitda_above_3m, crit.hq_north_america, crit.control_acquisition]:
        mark = {"Yes": "☑", "No": "☒", "Unclear": "◻"}.get(c.result.value, "◻")
        p = dc_left.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{mark}  {c.criterion} — {c.note}")
        r.font.size = Pt(9)
    for c in [crit.sponsor_angle, crit.seller_rollover, crit.hits_return_expectations]:
        mark = {"Yes": "☑", "No": "☒", "Unclear": "◻"}.get(c.result.value, "◻")
        p = dc_right.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{mark}  {c.criterion} — {c.note}")
        r.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # Company Overview (blue)
    def _co(cell):
        _add_text(cell, summary.company_overview.narrative)
        rev = summary.company_overview.revenue or "—"
        eb = summary.company_overview.ebitda or "—"
        p = cell.add_paragraph()
        run = p.add_run(f"Revenue: {rev}    |    EBITDA: {eb}")
        run.bold = True
        run.font.size = Pt(9)

    _box_table(doc, "Company Overview", _co, BLUE_BOX)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # Sources & Uses
    _sources_uses_table(doc, summary)

    doc.add_page_break()

    # === Page 2 ===
    # Highlights | Risks two-column
    t = doc.add_table(rows=1, cols=2)
    t.autofit = False
    t.columns[0].width = Cm(8.7)
    t.columns[1].width = Cm(8.7)
    left, right = t.rows[0].cells
    left.width = Cm(8.7)
    right.width = Cm(8.7)
    _shade(left, "FFFFFF")
    _shade(right, "FFFFFF")
    _heading(left, "Investment Highlights")
    _heading(right, "Investment Risks")
    _add_bullets(left, [p.bullet for p in summary.highlights_and_risks.highlights])
    _add_bullets(right, [p.bullet for p in summary.highlights_and_risks.risks])

    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    _box_table(
        doc, "Sponsor Value Creation Plan",
        lambda c: _add_bullets(c, summary.sponsor_value_creation.bullets),
        BLUE_BOX,
    )

    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # Industry / Competitors two-column (Page 2)
    ic = doc.add_table(rows=2, cols=2)
    ic.autofit = False
    ic.columns[0].width = Cm(8.75)
    ic.columns[1].width = Cm(8.75)
    _shade(ic.rows[0].cells[0], GRAY_BOX)
    _shade(ic.rows[0].cells[1], GRAY_BOX)
    _shade(ic.rows[1].cells[0], GRAY_BOX)
    _shade(ic.rows[1].cells[1], GRAY_BOX)
    _heading(ic.rows[0].cells[0], "Industry")
    _heading(ic.rows[0].cells[1], "Competitors")
    _add_text(ic.rows[1].cells[0], summary.industry_competitors.industry_overview)
    _add_text(ic.rows[1].cells[1], summary.industry_competitors.competitors)

    doc.add_page_break()

    # === Page 3 ===
    # Key Customers / Exit two-column
    t = doc.add_table(rows=2, cols=2)
    t.autofit = False
    t.columns[0].width = Cm(8.75)
    t.columns[1].width = Cm(8.75)
    _shade(t.rows[0].cells[0], GRAY_BOX)
    _shade(t.rows[0].cells[1], GRAY_BOX)
    _shade(t.rows[1].cells[0], GRAY_BOX)
    _shade(t.rows[1].cells[1], GRAY_BOX)
    _heading(t.rows[0].cells[0], "Key Customers / Projects")
    _heading(t.rows[0].cells[1], "Exit / Sponsor Returns")
    _add_text(t.rows[1].cells[0], summary.customers_and_exit.key_customers)
    _add_text(t.rows[1].cells[1], summary.customers_and_exit.exit_returns)

    doc.add_page_break()

    # === Page 4 ===
    _box_table(
        doc, "Other Considerations",
        lambda c: _add_text(c, summary.other_considerations.content),
        GREEN_BOX,
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    _box_table(
        doc, "Sponsor Overview",
        lambda c: _add_text(c, summary.sponsor_overview.content),
        BLUE_BOX,
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def _mgmt(cell):
        for b in summary.management_bios:
            p = cell.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(f"{b.name} — {b.title}")
            r.bold = True
            r.font.size = Pt(9)
            p2 = cell.add_paragraph()
            p2.paragraph_format.space_after = Pt(3)
            r2 = p2.add_run(b.summary)
            r2.font.size = Pt(9)
    _box_table(doc, "Management", _mgmt, "FFFFFF")

    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    _financials_table(doc, summary)

    # Footer
    for section in doc.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("  CONFIDENTIAL — TRISTONE STRATEGIC PARTNERS  ")
        run.bold = True
        run.font.size = Pt(8)
        run.font.color.rgb = WHITE
        # shade footer paragraph green
        pPr = footer._p.get_or_add_pPr()
        shd = etree.SubElement(pPr, qn("w:shd"))
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), GREEN_FOOTER)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def _sources_uses_table(doc, summary: CIMSummary) -> None:
    p = doc.add_paragraph()
    r = p.add_run("Sources & Uses")
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = NAVY
    r.font.underline = True

    su = summary.sources_and_uses
    num_src = len(su.sources)
    num_use = len(su.uses)
    data_rows = max(num_src, num_use)

    if data_rows == 0 and su.sources_total is None and su.uses_total is None:
        p2 = doc.add_paragraph()
        r2 = p2.add_run("Sources & Uses data not available in CIM.")
        r2.italic = True
        r2.font.size = Pt(9)
        return

    total_rows = 1 + data_rows + 1  # header + data + totals row
    t = doc.add_table(rows=total_rows, cols=6)
    t.autofit = False

    # Header row — navy background
    headers = ["Sources of Capital", "Amount ($M)", "Cumm. x EBITDA",
               "Uses of Capital", "Amount ($M)", "Cumm. x EBITDA"]
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _shade(c, "0E2A47")
        _set_cell_borders(c, "0E2A47")
        rr = c.paragraphs[0].add_run(h)
        rr.bold = True
        rr.font.size = Pt(8)
        rr.font.color.rgb = WHITE

    # Data rows
    for i in range(data_rows):
        row = t.rows[i + 1]
        for cell in row.cells:
            _set_cell_borders(cell, "D0D0D0")
        if i < num_src:
            s = su.sources[i]
            row.cells[0].paragraphs[0].add_run(s.item).font.size = Pt(8)
            if s.amount_m is not None:
                rr = row.cells[1].paragraphs[0].add_run(f"{s.amount_m:.1f}")
                rr.font.size = Pt(8)
                row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if s.multiple:
                rr = row.cells[2].paragraphs[0].add_run(s.multiple)
                rr.font.size = Pt(8)
                row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if i < num_use:
            u = su.uses[i]
            row.cells[3].paragraphs[0].add_run(u.item).font.size = Pt(8)
            if u.amount_m is not None:
                rr = row.cells[4].paragraphs[0].add_run(f"{u.amount_m:.1f}")
                rr.font.size = Pt(8)
                row.cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if u.multiple:
                rr = row.cells[5].paragraphs[0].add_run(u.multiple)
                rr.font.size = Pt(8)
                row.cells[5].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Totals row — light gray background
    tot = t.rows[-1]
    for c in tot.cells:
        _shade(c, "F2F2F2")
        _set_cell_borders(c, "BFBFBF")

    rs = tot.cells[0].paragraphs[0].add_run("Total Sources")
    rs.bold = True
    rs.font.size = Pt(8)
    if su.sources_total is not None:
        rv = tot.cells[1].paragraphs[0].add_run(f"{su.sources_total:.1f}")
        rv.bold = True
        rv.font.size = Pt(8)
        tot.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    ru = tot.cells[3].paragraphs[0].add_run("Total Uses")
    ru.bold = True
    ru.font.size = Pt(8)
    if su.uses_total is not None:
        rv = tot.cells[4].paragraphs[0].add_run(f"{su.uses_total:.1f}")
        rv.bold = True
        rv.font.size = Pt(8)
        tot.cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    if su.ltm_ebitda and su.sources_total:
        rr = tot.cells[2].paragraphs[0].add_run(f"{su.sources_total / su.ltm_ebitda:.1f}x")
        rr.font.size = Pt(8)
        tot.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if su.ltm_ebitda and su.uses_total:
        rr = tot.cells[5].paragraphs[0].add_run(f"{su.uses_total / su.ltm_ebitda:.1f}x")
        rr.font.size = Pt(8)
        tot.cells[5].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    if su.note:
        pn = doc.add_paragraph()
        rn = pn.add_run(f"* {su.note}")
        rn.italic = True
        rn.font.size = Pt(7)


def _financials_table(doc, summary: CIMSummary) -> None:
    p = doc.add_paragraph()
    r = p.add_run("Historical & Projected Financials")
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = NAVY
    r.font.underline = True

    fin = summary.financials
    cols: list[str] = []
    seen: set[str] = set()
    for row in fin.rows:
        for k in row.values.keys():
            if k not in seen:
                cols.append(k)
                seen.add(k)
    if not cols:
        doc.add_paragraph().add_run("No financial data extracted.").italic = True
        return

    has_hist_cagr = any(row.cagr for row in fin.rows)
    has_fore_cagr = any(row.cagr_forecasted for row in fin.rows)

    ncols = 1 + len(cols) + (1 if has_hist_cagr else 0) + (1 if has_fore_cagr else 0)
    t = doc.add_table(rows=1 + len(fin.rows), cols=ncols)
    t.autofit = False

    headers: list[str] = ["Metric"] + cols
    if has_hist_cagr:
        headers.append("Historical CAGR")
    if has_fore_cagr:
        headers.append("Forecasted CAGR")

    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _shade(c, "0E2A47")
        rr = c.paragraphs[0].add_run(h)
        rr.bold = True
        rr.font.size = Pt(9)
        rr.font.color.rgb = WHITE

    for ri, row in enumerate(fin.rows, start=1):
        cells = t.rows[ri].cells
        bg = "F5F5F5" if ("%" in row.metric or "Margin" in row.metric) else "FFFFFF"
        for c in cells:
            _shade(c, bg)
            _set_cell_borders(c, "D0D0D0")
        cells[0].paragraphs[0].add_run(row.metric).font.size = Pt(9)
        for ci, col in enumerate(cols, start=1):
            v = row.values.get(col)
            txt = "" if v is None else (f"{v:.1f}" if isinstance(v, (int, float)) else str(v))
            cells[ci].paragraphs[0].add_run(txt).font.size = Pt(9)
        col_offset = 1 + len(cols)
        if has_hist_cagr:
            cells[col_offset].paragraphs[0].add_run(row.cagr or "").font.size = Pt(9)
            col_offset += 1
        if has_fore_cagr:
            cells[col_offset].paragraphs[0].add_run(row.cagr_forecasted or "").font.size = Pt(9)
