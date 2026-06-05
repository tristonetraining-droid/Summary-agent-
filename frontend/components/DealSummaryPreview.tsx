"use client";
import type { CIMSummary } from "@/lib/types";
import { pageImageUrl } from "@/lib/api";

export function DealSummaryPreview({ summary, jobId }: { summary: CIMSummary; jobId: string }) {
  const s = summary;
  return (
    <div className="space-y-6">
      {/* === PAGE 1 === */}
      <div className="deal-page">
        <div className="deal-sidebar" />
        <div className="deal-body">
          <div className="flex items-end justify-between mb-2">
            <div>
              <div className="text-[20px] font-bold text-navy leading-tight">{s.header.project_name || "Project"}</div>
              <div className="text-[10px] text-gray-500">
                Sponsor: {s.header.sponsor_name || "—"} &nbsp;|&nbsp; {s.header.date || ""}
              </div>
            </div>
            <div className="text-[9px] text-gray-400">CIM Deal Summary</div>
          </div>

          <Box title="Deal Overview" tone="gray">
            {s.deal_overview.bullets.map((b, i) => <div className="bullet" key={i}>{b}</div>)}
          </Box>

          <Box title="Deal Criteria" tone="green">
            {Object.entries(s.deal_criteria).map(([k, c]: any) => (
              <div className="criterion-row" key={k}>
                <div>{c.result === "Yes" ? "☑" : c.result === "No" ? "☒" : "◻"}</div>
                <div><b>{c.criterion}</b> — <span className="text-gray-700">{c.note}</span></div>
                <div className="text-[9px] text-gray-500">{c.result}</div>
              </div>
            ))}
          </Box>

          <Box title="Company Overview" tone="blue">
            <div style={{ whiteSpace: "pre-wrap" }}>{s.company_overview.narrative}</div>
            <div className="font-semibold text-navy mt-1.5">
              Revenue: {s.company_overview.revenue || "—"} &nbsp;|&nbsp; EBITDA: {s.company_overview.ebitda || "—"}
            </div>
          </Box>

          <SourcesUsesView su={s.sources_and_uses} />
          <Footer />
        </div>
      </div>

      {/* === PAGE 2 === */}
      <div className="deal-page">
        <div className="deal-sidebar" />
        <div className="deal-body">
          <div className="text-[20px] font-bold text-navy mb-3">{s.header.project_name} — Highlights & Risks</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="section-head">Investment Highlights</div>
              {s.highlights_and_risks.highlights.map((p, i) => <div className="bullet" key={i}>{p.bullet}</div>)}
            </div>
            <div>
              <div className="section-head">Investment Risks</div>
              {s.highlights_and_risks.risks.map((p, i) => <div className="bullet" key={i}>{p.bullet}</div>)}
            </div>
          </div>
          <div className="h-3" />
          <Box title="Sponsor Value Creation Plan" tone="blue">
            {s.sponsor_value_creation.bullets.map((b, i) => <div className="bullet" key={i}>{b}</div>)}
          </Box>
          <Footer />
        </div>
      </div>

      {/* === PAGE 3 === */}
      <div className="deal-page">
        <div className="deal-sidebar" />
        <div className="deal-body">
          <Box title="Product Offering" tone="gray">
            <div className="mb-2">{s.product_offering.description}</div>
            <div className="grid grid-cols-3 gap-2">
              {s.product_offering.image_page_numbers.slice(0, 6).map((p) => (
                <img key={p} src={pageImageUrl(jobId, p)} alt={`p${p}`} className="w-full border" />
              ))}
            </div>
          </Box>

          <div className="grid grid-cols-2 gap-3">
            <Box title="Industry" tone="gray">
              <div style={{ whiteSpace: "pre-wrap" }}>{s.industry_competitors.industry_overview}</div>
            </Box>
            <Box title="Competitors" tone="gray">
              <div style={{ whiteSpace: "pre-wrap" }}>{s.industry_competitors.competitors}</div>
            </Box>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-2">
            <Box title="Key Customers / Projects" tone="gray">
              <div style={{ whiteSpace: "pre-wrap" }}>{s.customers_and_exit.key_customers}</div>
            </Box>
            <Box title="Exit / Sponsor Returns" tone="gray">
              <div style={{ whiteSpace: "pre-wrap" }}>{s.customers_and_exit.exit_returns}</div>
            </Box>
          </div>

          <Box title="Other Considerations" tone="green">
            <div style={{ whiteSpace: "pre-wrap" }}>{s.other_considerations.content}</div>
          </Box>
          <Box title="Sponsor Overview" tone="blue">
            <div style={{ whiteSpace: "pre-wrap" }}>{s.sponsor_overview.content}</div>
          </Box>

          <div className="section-head mt-2">Management</div>
          {s.management_bios.map((b, i) => (
            <div key={i} className="mb-1.5">
              <div><b>{b.name}</b> — {b.title}</div>
              <div className="text-gray-700">{b.summary}</div>
            </div>
          ))}
          <Footer />
        </div>
      </div>

      {/* === PAGE 4: Financials === */}
      <div className="deal-page">
        <div className="deal-sidebar" />
        <div className="deal-body">
          <div className="text-[18px] font-bold text-navy mb-3">Historical & Projected Financials</div>
          <FinancialsView fin={s.financials} />
          <Footer />
        </div>
      </div>
    </div>
  );
}

function Box({ title, tone, children }: { title: string; tone: "gray" | "green" | "blue"; children: any }) {
  return (
    <div className={`section-box box-${tone}`}>
      <div className="section-head">{title}</div>
      <div>{children}</div>
    </div>
  );
}

function Footer() {
  return <div className="deal-footer">CONFIDENTIAL — TRISTONE STRATEGIC PARTNERS</div>;
}

function SourcesUsesView({ su }: { su: CIMSummary["sources_and_uses"] }) {
  const rows = Math.max(su.sources.length, su.uses.length);
  return (
    <div className="mt-1">
      <div className="section-head">Sources & Uses {su.balanced ? "" : <span className="text-red-600 font-normal">(Unbalanced)</span>}</div>
      <table className="deal-table">
        <thead>
          <tr><th>Sources</th><th>$M</th><th>x LTM</th><th>Uses</th><th>$M</th><th>x LTM</th></tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => {
            const s = su.sources[i], u = su.uses[i];
            return (
              <tr key={i}>
                <td>{s?.item || ""}</td><td>{s?.amount_m?.toFixed(1) ?? ""}</td><td>{s?.multiple || ""}</td>
                <td>{u?.item || ""}</td><td>{u?.amount_m?.toFixed(1) ?? ""}</td><td>{u?.multiple || ""}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td>Total Sources</td><td>{su.sources_total?.toFixed(1) ?? ""}</td><td></td>
            <td>Total Uses</td><td>{su.uses_total?.toFixed(1) ?? ""}</td><td></td>
          </tr>
        </tfoot>
      </table>
      {su.note && <div className="text-[9px] text-gray-500 mt-1">{su.note}</div>}
    </div>
  );
}

function FinancialsView({ fin }: { fin: CIMSummary["financials"] }) {
  const cols: string[] = [];
  const seen = new Set<string>();
  for (const r of fin.rows) for (const k of Object.keys(r.values)) if (!seen.has(k)) { cols.push(k); seen.add(k); }
  if (!cols.length) return <div className="italic text-gray-500">No financial data extracted.</div>;
  return (
    <table className="deal-table fin-table">
      <thead>
        <tr>
          <th>Metric</th>
          {cols.map((c) => <th key={c}>{c}</th>)}
          <th>CAGR</th>
        </tr>
      </thead>
      <tbody>
        {fin.rows.map((r, i) => (
          <tr key={i}>
            <td>{r.metric}</td>
            {cols.map((c) => <td key={c}>{r.values[c] != null ? Number(r.values[c]).toFixed(1) : ""}</td>)}
            <td>{r.cagr || ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
