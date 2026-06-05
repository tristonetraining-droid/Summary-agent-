"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getHistorySummary, exportUrl, saveSummary } from "@/lib/api";
import type { SavedSummary, CIMSummary } from "@/lib/types";
import { DealSummaryPreview } from "@/components/DealSummaryPreview";
import { SectionEditors } from "@/components/SectionEditors";
import { toast } from "sonner";
import { ArrowLeft, FileDown, Printer, Loader2, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

function formatSavedAt(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function HistoryViewPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();

  const [record, setRecord] = useState<SavedSummary | null>(null);
  const [summary, setSummary] = useState<CIMSummary | null>(null);
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);

  useEffect(() => {
    getHistorySummary(id)
      .then((r) => { setRecord(r); setSummary(r.summary); })
      .catch((e) => toast.error("Failed to load: " + (e?.message || "")));
  }, [id]);

  async function doExport(format: "docx" | "pdf") {
    if (!summary || !record) return;
    setExporting(format);
    try {
      await saveSummary(record.job_id, summary);
      const res = await fetch(exportUrl(record.job_id, format), { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CIM_Summary_${record.deal_name}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error("Export failed: " + (e?.message || ""));
    } finally {
      setExporting(null);
    }
  }

  if (!record || !summary) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading saved summary…
      </div>
    );
  }

  return (
    <div className="-mt-4">
      <div className="sticky top-14 z-20 -mx-6 px-6 py-3 bg-background/85 backdrop-blur-md border-b border-border flex items-center justify-between no-print">
        <div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.back()}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Back"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="font-semibold tracking-tight">{record.deal_name}</span>
            <span className="text-xs rounded-full bg-muted px-2 py-0.5 text-muted-foreground">Archived</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5 ml-6">
            <Clock className="w-3 h-3" />
            Saved {formatSavedAt(record.saved_at)}
            {record.sponsor_name && <> · {record.sponsor_name}</>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Printer className="w-3.5 h-3.5" /> Print
          </Button>
          <Button variant="outline" size="sm" onClick={() => doExport("docx")} disabled={!!exporting}>
            <FileDown className="w-3.5 h-3.5" />
            {exporting === "docx" ? "Exporting…" : "DOCX"}
          </Button>
          <Button size="sm" onClick={() => doExport("pdf")} disabled={!!exporting}>
            <FileDown className="w-3.5 h-3.5" />
            {exporting === "pdf" ? "Exporting…" : "Export PDF"}
          </Button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1.05fr_1fr] gap-6 mt-6">
        <div className="overflow-x-auto">
          <DealSummaryPreview summary={summary} jobId={record.job_id} />
        </div>
        <div className="no-print">
          <div className="text-sm text-muted-foreground mb-3">
            This is a saved snapshot. Edits here will not affect the original job.
          </div>
          <SectionEditors summary={summary} jobId={record.job_id} onChange={setSummary} />
        </div>
      </div>
    </div>
  );
}
