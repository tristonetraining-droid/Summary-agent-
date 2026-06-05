"use client";
import { useState } from "react";
import type { CIMSummary, DealCriterion, ManagementBio, FinancialRow, SourcesUsesItem, YesNo } from "@/lib/types";
import { pageImageUrl } from "@/lib/api";
import { Plus, Trash2, GripVertical, ChevronDown, ChevronRight } from "lucide-react";

type Update = (next: CIMSummary) => void;

export function SectionEditors({ summary, jobId, onChange }: { summary: CIMSummary; jobId: string; onChange: Update }) {
  return (
    <div className="space-y-3">
      <Section title="Deal Header" defaultOpen>
        <DealHeaderEditor s={summary} onChange={onChange} />
      </Section>

      <Section title="Deal Overview">
        <BulletEditor
          bullets={summary.deal_overview.bullets}
          onChange={(b) => onChange({ ...summary, deal_overview: { bullets: b } })}
          max={5}
        />
      </Section>

      <Section title="Deal Criteria">
        <CriteriaEditor s={summary} onChange={onChange} />
      </Section>

      <Section title="Company Overview">
        <TextArea
          value={summary.company_overview.narrative}
          onChange={(v) => onChange({ ...summary, company_overview: { ...summary.company_overview, narrative: v } })}
          rows={5}
        />
        <div className="grid grid-cols-2 gap-2 mt-2">
          <TextField label="Revenue (LTM)" value={summary.company_overview.revenue || ""}
            onChange={(v) => onChange({ ...summary, company_overview: { ...summary.company_overview, revenue: v } })} />
          <TextField label="EBITDA (LTM)" value={summary.company_overview.ebitda || ""}
            onChange={(v) => onChange({ ...summary, company_overview: { ...summary.company_overview, ebitda: v } })} />
        </div>
      </Section>

      <Section title="Sources & Uses">
        <SourcesUsesEditor s={summary} onChange={onChange} />
      </Section>

      <Section title="Investment Highlights">
        <BulletEditor
          bullets={summary.highlights_and_risks.highlights.map((h) => h.bullet)}
          onChange={(arr) => onChange({
            ...summary,
            highlights_and_risks: { ...summary.highlights_and_risks, highlights: arr.map((b) => ({ bullet: b })) },
          })}
          max={5}
        />
      </Section>

      <Section title="Investment Risks">
        <BulletEditor
          bullets={summary.highlights_and_risks.risks.map((h) => h.bullet)}
          onChange={(arr) => onChange({
            ...summary,
            highlights_and_risks: { ...summary.highlights_and_risks, risks: arr.map((b) => ({ bullet: b })) },
          })}
          max={5}
        />
      </Section>

      <Section title="Sponsor Value Creation">
        <BulletEditor
          bullets={summary.sponsor_value_creation.bullets}
          onChange={(b) => onChange({ ...summary, sponsor_value_creation: { bullets: b } })}
          max={6}
        />
      </Section>

      <Section title="Product Offering">
        <TextArea
          value={summary.product_offering.description || ""}
          onChange={(v) => onChange({ ...summary, product_offering: { ...summary.product_offering, description: v } })}
          rows={3}
        />
        <ProductImagePicker s={summary} jobId={jobId} onChange={onChange} />
      </Section>

      <Section title="Industry & Competitors">
        <TextField label="Industry overview" value={summary.industry_competitors.industry_overview}
          onChange={(v) => onChange({ ...summary, industry_competitors: { ...summary.industry_competitors, industry_overview: v } })}
          textarea rows={4}
        />
        <TextField label="Competitors" value={summary.industry_competitors.competitors}
          onChange={(v) => onChange({ ...summary, industry_competitors: { ...summary.industry_competitors, competitors: v } })}
          textarea rows={4}
        />
      </Section>

      <Section title="Customers & Exit">
        <TextField label="Key customers" value={summary.customers_and_exit.key_customers}
          onChange={(v) => onChange({ ...summary, customers_and_exit: { ...summary.customers_and_exit, key_customers: v } })}
          textarea rows={4}
        />
        <TextField label="Exit / Sponsor returns" value={summary.customers_and_exit.exit_returns}
          onChange={(v) => onChange({ ...summary, customers_and_exit: { ...summary.customers_and_exit, exit_returns: v } })}
          textarea rows={3}
        />
      </Section>

      <Section title="Other Considerations">
        <TextArea
          value={summary.other_considerations.content}
          onChange={(v) => onChange({ ...summary, other_considerations: { content: v } })}
          rows={4}
        />
      </Section>

      <Section title="Sponsor Overview">
        <TextArea
          value={summary.sponsor_overview.content}
          onChange={(v) => onChange({ ...summary, sponsor_overview: { content: v } })}
          rows={4}
        />
      </Section>

      <Section title="Management Bios">
        <ManagementEditor bios={summary.management_bios}
          onChange={(b) => onChange({ ...summary, management_bios: b })} />
      </Section>

      <Section title="Financials">
        <FinancialsEditor s={summary} onChange={onChange} />
      </Section>
    </div>
  );
}

// --- Primitives ---

function Section({ title, defaultOpen, children }: { title: string; defaultOpen?: boolean; children: any }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="border border-border rounded-lg bg-card text-card-foreground shadow-sm">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-muted/50 rounded-lg transition-colors">
        <span className="font-medium">{title}</span>
        {open ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
      </button>
      {open && <div className="px-4 pb-4 border-t border-border pt-3">{children}</div>}
    </div>
  );
}

function TextField({ label, value, onChange, textarea, rows = 2 }:
  { label: string; value: string; onChange: (v: string) => void; textarea?: boolean; rows?: number }) {
  return (
    <label className="block mb-2">
      <span className="block text-xs text-muted-foreground mb-1">{label}</span>
      {textarea
        ? <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={rows}
            className="w-full text-sm rounded-md border border-input bg-card px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring" />
        : <input value={value} onChange={(e) => onChange(e.target.value)}
            className="w-full text-sm rounded-md border border-input bg-card px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring" />}
    </label>
  );
}

function TextArea({ value, onChange, rows = 4 }: { value: string; onChange: (v: string) => void; rows?: number }) {
  return (
    <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={rows}
      className="w-full text-sm rounded-md border border-input bg-card px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring" />
  );
}

function BulletEditor({ bullets, onChange, max = 5 }:
  { bullets: string[]; onChange: (b: string[]) => void; max?: number }) {
  return (
    <div className="space-y-2 mt-1">
      {bullets.map((b, i) => (
        <div key={i} className="flex gap-2 items-start">
          <GripVertical className="w-4 h-4 text-muted-foreground mt-2" />
          <textarea value={b} onChange={(e) => {
              const c = [...bullets]; c[i] = e.target.value; onChange(c);
            }}
            rows={2}
            className="flex-1 text-sm rounded-md border border-input bg-card px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button onClick={() => onChange(bullets.filter((_, j) => j !== i))}
            className="text-muted-foreground hover:text-destructive mt-1.5 transition-colors">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      {bullets.length < max && (
        <button onClick={() => onChange([...bullets, ""])}
          className="text-sm text-foreground hover:underline inline-flex items-center gap-1">
          <Plus className="w-4 h-4" /> Add bullet
        </button>
      )}
    </div>
  );
}

function DealHeaderEditor({ s, onChange }: { s: CIMSummary; onChange: Update }) {
  return (
    <div className="grid grid-cols-3 gap-3 mt-2">
      <TextField label="Project name" value={s.header.project_name}
        onChange={(v) => onChange({ ...s, header: { ...s.header, project_name: v } })} />
      <TextField label="Sponsor" value={s.header.sponsor_name}
        onChange={(v) => onChange({ ...s, header: { ...s.header, sponsor_name: v } })} />
      <TextField label="Date" value={s.header.date}
        onChange={(v) => onChange({ ...s, header: { ...s.header, date: v } })} />
    </div>
  );
}

function CriteriaEditor({ s, onChange }: { s: CIMSummary; onChange: Update }) {
  const keys = Object.keys(s.deal_criteria) as (keyof CIMSummary["deal_criteria"])[];
  return (
    <div className="space-y-2 mt-2">
      {keys.map((k) => {
        const c: DealCriterion = (s.deal_criteria as any)[k];
        return (
          <div key={k} className="grid grid-cols-[1fr_120px] gap-2 items-start">
            <div>
              <div className="text-xs font-medium text-foreground">{c.criterion}</div>
              <input value={c.note} placeholder="Note / evidence"
                onChange={(e) => onChange({
                  ...s,
                  deal_criteria: { ...s.deal_criteria, [k]: { ...c, note: e.target.value } } as any,
                })}
                className="mt-1 w-full text-sm rounded-md border border-input bg-card px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <select value={c.result}
              onChange={(e) => onChange({
                ...s,
                deal_criteria: { ...s.deal_criteria, [k]: { ...c, result: e.target.value as YesNo } } as any,
              })}
              className="rounded-md border border-input bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="Yes">Yes</option>
              <option value="No">No</option>
              <option value="Unclear">Unclear</option>
            </select>
          </div>
        );
      })}
    </div>
  );
}

function SourcesUsesEditor({ s, onChange }: { s: CIMSummary; onChange: Update }) {
  const su = s.sources_and_uses;
  function setItems(which: "sources" | "uses", items: SourcesUsesItem[]) {
    const total = items.reduce((a, b) => a + (b.amount_m || 0), 0);
    const next = { ...su, [which]: items, [`${which}_total`]: items.length ? total : null };
    next.balanced = !!(next.sources_total && next.uses_total) && Math.abs((next.sources_total || 0) - (next.uses_total || 0)) <= 0.5;
    onChange({ ...s, sources_and_uses: next as any });
  }
  function row(which: "sources" | "uses", item: SourcesUsesItem, i: number) {
    const arr = which === "sources" ? su.sources : su.uses;
    return (
      <div key={i} className="grid grid-cols-[1fr_80px_80px_28px] gap-1.5 mb-1">
        <input value={item.item} placeholder="Item"
          onChange={(e) => { const a = [...arr]; a[i] = { ...item, item: e.target.value }; setItems(which, a); }}
          className="text-xs rounded border px-2 py-1" />
        <input value={item.amount_m ?? ""} placeholder="$M" type="number" step="0.1"
          onChange={(e) => { const a = [...arr]; a[i] = { ...item, amount_m: e.target.value === "" ? null : Number(e.target.value) }; setItems(which, a); }}
          className="text-xs rounded border px-2 py-1" />
        <input value={item.multiple || ""} placeholder="x LTM"
          onChange={(e) => { const a = [...arr]; a[i] = { ...item, multiple: e.target.value || null }; setItems(which, a); }}
          className="text-xs rounded border px-2 py-1" />
        <button onClick={() => setItems(which, arr.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-600">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 mt-2">
      <div>
        <div className="text-xs font-semibold text-navy mb-1">Sources</div>
        {su.sources.map((it, i) => row("sources", it, i))}
        <button onClick={() => setItems("sources", [...su.sources, { item: "", amount_m: null, multiple: null }])}
          className="text-xs text-navy hover:underline inline-flex items-center gap-1">
          <Plus className="w-3 h-3" /> Add source
        </button>
        <div className="text-xs mt-1.5 text-gray-600">Total: <b>{su.sources_total?.toFixed(1) ?? "—"}</b></div>
      </div>
      <div>
        <div className="text-xs font-semibold text-navy mb-1">Uses</div>
        {su.uses.map((it, i) => row("uses", it, i))}
        <button onClick={() => setItems("uses", [...su.uses, { item: "", amount_m: null, multiple: null }])}
          className="text-xs text-navy hover:underline inline-flex items-center gap-1">
          <Plus className="w-3 h-3" /> Add use
        </button>
        <div className="text-xs mt-1.5 text-gray-600">
          Total: <b>{su.uses_total?.toFixed(1) ?? "—"}</b>
          {!su.balanced && (su.sources_total || su.uses_total) && (
            <span className="ml-2 text-red-600">Unbalanced</span>
          )}
        </div>
      </div>
    </div>
  );
}

function ProductImagePicker({ s, jobId, onChange }: { s: CIMSummary; jobId: string; onChange: Update }) {
  const selected = new Set(s.product_offering.image_page_numbers);
  const candidates = Array.from(new Set(s.product_offering.image_page_numbers)).sort((a, b) => a - b);
  // also allow user to enter additional page numbers
  const [extra, setExtra] = useState("");
  function toggle(p: number) {
    const next = new Set(selected);
    next.has(p) ? next.delete(p) : next.add(p);
    onChange({ ...s, product_offering: { ...s.product_offering, image_page_numbers: Array.from(next).sort((a, b) => a - b) } });
  }
  function addExtra() {
    const n = parseInt(extra, 10);
    if (!isNaN(n) && n > 0 && !selected.has(n)) toggle(n);
    setExtra("");
  }
  return (
    <div className="mt-2">
      <div className="text-xs text-gray-600 mb-1">Selected pages for product image grid (click to toggle):</div>
      <div className="grid grid-cols-4 gap-2">
        {candidates.map((p) => (
          <button key={p} onClick={() => toggle(p)}
            className={"relative border rounded overflow-hidden " + (selected.has(p) ? "ring-2 ring-navy" : "opacity-70 hover:opacity-100")}>
            <img src={pageImageUrl(jobId, p)} alt={`p${p}`} className="w-full" />
            <span className="absolute top-1 left-1 text-[10px] bg-white/90 px-1 rounded">p.{p}</span>
          </button>
        ))}
      </div>
      <div className="flex gap-2 mt-2">
        <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Add page # from CIM"
          className="text-xs rounded border px-2 py-1 w-40" />
        <button onClick={addExtra} className="text-xs text-navy hover:underline">Add</button>
      </div>
    </div>
  );
}

function ManagementEditor({ bios, onChange }: { bios: ManagementBio[]; onChange: (b: ManagementBio[]) => void }) {
  return (
    <div className="space-y-2 mt-2">
      {bios.map((b, i) => (
        <div key={i} className="border rounded p-2">
          <div className="grid grid-cols-2 gap-2 mb-1">
            <input value={b.name} placeholder="Name"
              onChange={(e) => { const c = [...bios]; c[i] = { ...b, name: e.target.value }; onChange(c); }}
              className="text-sm rounded border px-2 py-1" />
            <input value={b.title} placeholder="Title"
              onChange={(e) => { const c = [...bios]; c[i] = { ...b, title: e.target.value }; onChange(c); }}
              className="text-sm rounded border px-2 py-1" />
          </div>
          <textarea value={b.summary} placeholder="Bio" rows={2}
            onChange={(e) => { const c = [...bios]; c[i] = { ...b, summary: e.target.value }; onChange(c); }}
            className="w-full text-sm rounded border px-2 py-1" />
          <button onClick={() => onChange(bios.filter((_, j) => j !== i))}
            className="text-xs text-gray-500 hover:text-red-600 mt-1 inline-flex items-center gap-1">
            <Trash2 className="w-3 h-3" /> Remove
          </button>
        </div>
      ))}
      <button onClick={() => onChange([...bios, { name: "", title: "", summary: "" }])}
        className="text-sm text-navy hover:underline inline-flex items-center gap-1">
        <Plus className="w-4 h-4" /> Add bio
      </button>
    </div>
  );
}

function FinancialsEditor({ s, onChange }: { s: CIMSummary; onChange: Update }) {
  const fin = s.financials;
  const cols: string[] = [];
  const seen = new Set<string>();
  for (const r of fin.rows) for (const k of Object.keys(r.values)) if (!seen.has(k)) { cols.push(k); seen.add(k); }

  function setRows(rows: FinancialRow[]) {
    onChange({ ...s, financials: { ...fin, rows } });
  }
  function addCol() {
    const name = prompt("Column name (e.g., FY2025P)");
    if (!name) return;
    const next = fin.rows.map((r) => ({ ...r, values: { ...r.values, [name]: null } }));
    setRows(next);
  }
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="text-xs w-full">
        <thead>
          <tr className="bg-gray-50">
            <th className="text-left p-1 border">Metric</th>
            {cols.map((c) => <th key={c} className="p-1 border">{c}</th>)}
            <th className="p-1 border">CAGR</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {fin.rows.map((r, i) => (
            <tr key={i}>
              <td className="p-0.5 border">
                <input value={r.metric}
                  onChange={(e) => { const c = [...fin.rows]; c[i] = { ...r, metric: e.target.value }; setRows(c); }}
                  className="w-full px-1 py-0.5" />
              </td>
              {cols.map((col) => (
                <td key={col} className="p-0.5 border">
                  <input value={r.values[col] ?? ""} type="number" step="0.1"
                    onChange={(e) => {
                      const c = [...fin.rows];
                      c[i] = { ...r, values: { ...r.values, [col]: e.target.value === "" ? null : Number(e.target.value) } };
                      setRows(c);
                    }}
                    className="w-20 px-1 py-0.5" />
                </td>
              ))}
              <td className="p-0.5 border">
                <input value={r.cagr || ""}
                  onChange={(e) => { const c = [...fin.rows]; c[i] = { ...r, cagr: e.target.value || null }; setRows(c); }}
                  className="w-16 px-1 py-0.5" />
              </td>
              <td className="p-0.5">
                <button onClick={() => setRows(fin.rows.filter((_, j) => j !== i))}
                  className="text-gray-400 hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-2">
        <button onClick={() => setRows([...fin.rows, { metric: "", values: Object.fromEntries(cols.map((c) => [c, null])), cagr: null }])}
          className="text-xs text-navy hover:underline inline-flex items-center gap-1">
          <Plus className="w-3 h-3" /> Add row
        </button>
        <button onClick={addCol} className="text-xs text-navy hover:underline inline-flex items-center gap-1">
          <Plus className="w-3 h-3" /> Add column
        </button>
      </div>
    </div>
  );
}
