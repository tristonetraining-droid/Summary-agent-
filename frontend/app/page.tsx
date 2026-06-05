"use client";
import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, FileText, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { createJob } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function Home() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [dealName, setDealName] = useState("");
  const [sponsor, setSponsor] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.toLowerCase().endsWith(".pdf")) setFile(f);
    else toast.error("Drop a PDF file");
  }

  async function submit() {
    if (!file) return toast.error("Choose a CIM PDF");
    if (!dealName.trim()) return toast.error("Enter a deal name");
    setBusy(true);
    try {
      const { id } = await createJob(file, dealName.trim(), sponsor.trim());
      router.push(`/jobs/${id}`);
    } catch (e: any) {
      toast.error(e?.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid lg:grid-cols-[1.1fr_1fr] gap-10 mt-8">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground mb-5">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          AI pipeline online
        </div>
        <h1 className="text-4xl font-bold tracking-tight">
          Turn a CIM into a Deal Summary <br/>in under 3 minutes.
        </h1>
        <p className="mt-4 text-muted-foreground leading-relaxed max-w-md">
          Upload a Confidential Information Memorandum. CIMSummarizer extracts the 11
          required sections, strips marketing language, and gives you a fully editable
          4-page Deal Summary you can export as DOCX or PDF.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New Deal Summary</CardTitle>
          <CardDescription>Step 1 of 1 — upload CIM</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={
              "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors " +
              (drag
                ? "border-ring bg-muted"
                : "border-border hover:border-ring hover:bg-muted/60")
            }
          >
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="text-left">
                  <div className="font-medium">{file.name}</div>
                  <div className="text-xs text-muted-foreground">{(file.size / (1024 * 1024)).toFixed(1)} MB</div>
                </div>
              </div>
            ) : (
              <>
                <UploadCloud className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <div className="font-medium">Drop CIM PDF here, or click to browse</div>
                <div className="text-xs text-muted-foreground mt-1">Up to 200 pages, ~50MB</div>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="block text-muted-foreground mb-1.5">Deal name</span>
              <input
                type="text"
                value={dealName}
                onChange={(e) => setDealName(e.target.value)}
                placeholder="Project Tailwind"
                className="w-full h-9 rounded-md border border-input bg-card px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <label className="text-sm">
              <span className="block text-muted-foreground mb-1.5">Sponsor / Seller</span>
              <input
                type="text"
                value={sponsor}
                onChange={(e) => setSponsor(e.target.value)}
                placeholder="ABC Capital"
                className="w-full h-9 rounded-md border border-input bg-card px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          </div>

          <Button
            onClick={submit}
            disabled={busy || !file || !dealName.trim()}
            className="w-full h-10"
          >
            {busy ? "Uploading…" : (<>Start summarization <ArrowRight className="w-4 h-4" /></>)}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
