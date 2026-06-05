import type { CIMSummary, JobState, SavedSummaryMeta, SavedSummary } from "./types";

export async function createJob(file: File, dealName: string, sponsorName: string): Promise<{ id: string }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("deal_name", dealName);
  fd.append("sponsor_name", sponsorName);
  const res = await fetch("/api/jobs", { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function getJob(id: string): Promise<JobState> {
  const res = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
}

export async function saveSummary(id: string, summary: CIMSummary): Promise<void> {
  const res = await fetch(`/api/jobs/${id}/summary`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(summary),
  });
  if (!res.ok) throw new Error(`Save failed: ${res.status}`);
}

export function pageImageUrl(id: string, n: number): string {
  return `/api/jobs/${id}/cim-page/${n}.png`;
}

export function exportUrl(id: string, format: "docx" | "pdf"): string {
  return `/api/jobs/${id}/export?format=${format}`;
}

export function cn(...xs: (string | false | null | undefined)[]) {
  return xs.filter(Boolean).join(" ");
}

export async function saveToHistory(jobId: string): Promise<SavedSummaryMeta> {
  const res = await fetch(`/api/jobs/${jobId}/save-to-history`, { method: "POST" });
  if (!res.ok) throw new Error(`Save to history failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function listHistory(): Promise<SavedSummaryMeta[]> {
  const res = await fetch("/api/summaries", { cache: "no-store" });
  if (!res.ok) throw new Error(`Fetch history failed: ${res.status}`);
  return res.json();
}

export async function getHistorySummary(id: string): Promise<SavedSummary> {
  const res = await fetch(`/api/summaries/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Fetch summary failed: ${res.status}`);
  return res.json();
}
