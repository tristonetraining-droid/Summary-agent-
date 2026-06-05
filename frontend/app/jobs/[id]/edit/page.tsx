"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { getJob, saveSummary, exportUrl, saveToHistory } from "@/lib/api";
import type { CIMSummary, JobState } from "@/lib/types";
import { DealSummaryPreview } from "@/components/DealSummaryPreview";
import { SectionEditors } from "@/components/SectionEditors";
import { toast } from "sonner";
import { BookmarkPlus, FileDown, Printer, Loader2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function EditPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [job, setJob] = useState<JobState | null>(null);
  const [summary, setSummary] = useState<CIMSummary | null>(null);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [archived, setArchived] = useState(false);
  const debounceRef = useRef<any>(null);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const previewInnerRef = useRef<HTMLDivElement>(null);

  const applyPreviewScale = useCallback(() => {
    const container = previewContainerRef.current;
    const inner = previewInnerRef.current;
    if (!container || !inner) return;
    const scale = container.offsetWidth / 794;
    inner.style.transform = `scale(${scale})`;
    inner.style.height = `${container.offsetHeight / scale}px`;
  }, []);

  useEffect(() => {
    applyPreviewScale();
    const ro = new ResizeObserver(applyPreviewScale);
    if (previewContainerRef.current) ro.observe(previewContainerRef.current);
    window.addEventListener("resize", applyPreviewScale);
    return () => { ro.disconnect(); window.removeEventListener("resize", applyPreviewScale); };
  }, [applyPreviewScale, summary]);

  useEffect(() => {
    getJob(id).then((j) => { setJob(j); if (j.summary) setSummary(j.summary); }).catch(() => {});
  }, [id]);

  // Autosave debounced
  useEffect(() => {
    if (!summary) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        setSaving(true);
        await saveSummary(id, summary);
      } catch (e: any) {
        toast.error("Save failed: " + (e?.message || ""));
      } finally {
        setSaving(false);
      }
    }, 800);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [summary, id]);

  async function doArchive() {
    setArchiving(true);
    try {
      await saveToHistory(id);
      setArchived(true);
      setTimeout(() => setArchived(false), 3000);
    } catch (e: any) {
      toast.error("Save to history failed: " + (e?.message || ""));
    } finally {
      setArchiving(false);
    }
  }

  async function doExport(format: "docx" | "pdf") {
    if (!summary) return;
    setExporting(format);
    try {
      // Ensure latest saved
      await saveSummary(id, summary);
      const res = await fetch(exportUrl(id, format), { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CIM_Summary_${job?.deal_name || "Deal"}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error("Export failed: " + (e?.message || ""));
    } finally {
      setExporting(null);
    }
  }

  if (!job || !summary) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading deal summary…
      </div>
    );
  }

  return (
    <div className="-mt-4">
      <div className="sticky top-14 z-20 -mx-6 px-6 py-3 bg-background/85 backdrop-blur-md border-b border-border flex items-center justify-between no-print">
        <div>
          <div className="font-semibold tracking-tight">{job.deal_name}</div>
          <div className="text-xs text-muted-foreground flex items-center gap-1.5">
            <span className={"inline-block h-1.5 w-1.5 rounded-full " + (saving ? "bg-amber-500 animate-pulse" : "bg-success")} />
            {saving ? "Saving…" : "All changes saved"} · {job.filename}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={doArchive}
            disabled={archiving}
            title="Save a snapshot to history"
          >
            {archived
              ? <><Check className="w-3.5 h-3.5 text-green-500" /> Saved!</>
              : archiving
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…</>
              : <><BookmarkPlus className="w-3.5 h-3.5" /> Save to History</>}
          </Button>
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

      <div style={{ display: "flex", gap: 0, marginTop: 24, alignItems: "flex-start" }}>
        {/* ── LEFT: Preview ── takes 58vw, scales content to fill */}
        <div
          className="hidden lg:block shrink-0"
          style={{
            width: "58vw",
            position: "sticky",
            top: 110,
            maxHeight: "calc(100vh - 118px)",
            overflow: "hidden",
            borderRight: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          {/*
            The preview renders at ~794px (A4 width).
            We scale it so it fills the 58vw column:
            scale = 58vw / 794px  →  use CSS calc via scaleX trick.
            Since CSS can't divide vw by px directly, we use a wrapper
            with width:794px scaled via zoom-like transform on a
            container div sized to exactly 58vw.
          */}
          <div ref={previewContainerRef} style={{ width: "100%", height: "calc(100vh - 118px)", overflowY: "hidden", overflowX: "hidden", position: "relative" }}>
            <div ref={previewInnerRef} style={{ transformOrigin: "top left", width: 794, position: "absolute", top: 0, left: 0, overflowY: "auto" }}>
              <DealSummaryPreview summary={summary} jobId={id} />
            </div>
          </div>
        </div>

        {/* ── RIGHT: Editor panel ── fills the remaining ~42vw */}
        <div
          className="flex-1 min-w-0 no-print"
          style={{
            paddingLeft: 24,
            paddingRight: 4,
            maxHeight: "calc(100vh - 118px)",
            overflowY: "auto",
            minWidth: 320,
          }}
        >
          <p className="text-sm text-muted-foreground mb-4">
            Edit the deal summary — the preview updates live. Exports use the latest edits.
          </p>
          <SectionEditors summary={summary} jobId={id} onChange={setSummary} />
        </div>
      </div>
    </div>
  );
}
