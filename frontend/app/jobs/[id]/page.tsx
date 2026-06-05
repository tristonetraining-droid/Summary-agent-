"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJob } from "@/lib/api";
import type { JobStage, JobState, StageEvent } from "@/lib/types";
import { CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { AnimateNumber } from "@/components/ui/animated-blur-number";

const STAGES: { key: JobStage; label: string; desc: string; weight: number }[] = [
  { key: "ingest",     label: "Ingest",                desc: "Reading & parsing PDF pages…",              weight: 15  },
  { key: "classify",  label: "Classify Sections",      desc: "Mapping CIM sections with AI…",             weight: 15  },
  { key: "extract",   label: "Extract (11 sections)",  desc: "Extracting deal data in parallel…",         weight: 40  },
  { key: "synthesize",label: "Tone + Consistency",     desc: "Reviewing tone & fixing inconsistencies…",  weight: 15  },
  { key: "assemble",  label: "Assemble DOCX",          desc: "Building formatted Word document…",         weight: 10  },
  { key: "done",      label: "Done",                   desc: "Complete!",                                 weight: 5   },
];

// Map queued → treat as ingest starting
function resolveStageIdx(stage: JobStage): number {
  if (stage === "queued") return 0;
  const idx = STAGES.findIndex((s) => s.key === stage);
  return idx >= 0 ? idx : 0;
}

export default function JobProgress() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const [job, setJob] = useState<JobState | null>(null);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [realProgress, setRealProgress] = useState(0);
  const [displayProgress, setDisplayProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState<JobStage>("queued");
  const [lastMessage, setLastMessage] = useState("");
  const [gotRealEvent, setGotRealEvent] = useState(false);
  const trickleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Smooth trickle toward realProgress
  useEffect(() => {
    if (trickleRef.current) clearInterval(trickleRef.current);
    trickleRef.current = setInterval(() => {
      setDisplayProgress((prev) => {
        if (prev >= realProgress) return prev;
        const step = Math.max(0.0015, (realProgress - prev) * 0.07);
        return Math.min(prev + step, realProgress);
      });
    }, 40);
    return () => { if (trickleRef.current) clearInterval(trickleRef.current); };
  }, [realProgress]);

  // Startup idle trickle: if no real events yet, slowly walk progress up to ~4%
  useEffect(() => {
    if (gotRealEvent) return;
    const timer = setInterval(() => {
      setRealProgress((prev) => {
        if (prev >= 0.04) return prev;
        return prev + 0.002;
      });
    }, 200);
    return () => clearInterval(timer);
  }, [gotRealEvent]);

  useEffect(() => {
    let cancelled = false;
    getJob(id).then((j) => {
      if (cancelled) return;
      setJob(j);
      if (j.stage === "done") {
        setCurrentStage("done");
        setRealProgress(1);
        setDisplayProgress(1);
      } else if (j.stage !== "queued") {
        setCurrentStage(j.stage);
        setGotRealEvent(true);
      }
    }).catch(() => {});

    const es = new EventSource(`/api/jobs/${id}/events`);
    es.addEventListener("stage", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as StageEvent;
        setEvents((prev) => [...prev, data]);
        setCurrentStage(data.stage);
        setLastMessage(data.message);
        setGotRealEvent(true);
        if (typeof data.progress === "number") setRealProgress(data.progress);
        if (data.stage === "done") {
          setRealProgress(1);
          setDisplayProgress(1);
          es.close();
          getJob(id).then((j) => { if (!cancelled) setJob(j); }).finally(() => {
            setTimeout(() => router.push(`/jobs/${id}/edit`), 800);
          });
        }
        if (data.stage === "error") {
          es.close();
          getJob(id).then((j) => { if (!cancelled) setJob(j); });
        }
      } catch {}
    });
    es.onerror = () => es.close();
    return () => { cancelled = true; es.close(); };
  }, [id, router]);

  const stageIdx = resolveStageIdx(currentStage);
  const pct = Math.round(displayProgress * 100);
  const isError = currentStage === "error";
  const isDone  = currentStage === "done";
  const activeDesc = lastMessage || STAGES[stageIdx]?.desc || "Working…";

  return (
    <div className="max-w-2xl mx-auto mt-10">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{job?.deal_name || "Processing…"}</h1>
          <p className="text-sm text-muted-foreground mt-1">{job?.filename}</p>
        </div>
        <div className="flex items-baseline gap-1">
          <AnimateNumber value={pct} className="text-5xl font-bold tracking-tight" />
          <span className="text-xl text-muted-foreground">%</span>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6 pb-6">

          {/* ── Progress bar ── */}
          <div className="relative h-3 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-300 ease-out"
              style={{
                width: `${Math.max(pct, 2)}%`,
                background: isDone
                  ? "linear-gradient(90deg,#10b981,#34d399)"
                  : "linear-gradient(90deg,#3b82f6,#60a5fa,#34d399)",
              }}
            >
              {/* shimmer sweep */}
              {!isDone && (
                <div
                  style={{
                    position: "absolute", top: 0, left: "-100%", width: "60%", height: "100%",
                    background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.35),transparent)",
                    animation: "shimmer 1.6s infinite",
                  }}
                />
              )}
            </div>
          </div>

          {/* ── Active message ── */}
          {!isDone && !isError && (
            <p className="mt-2.5 text-xs text-muted-foreground" style={{ minHeight: 18 }}>
              {activeDesc}
            </p>
          )}

          {/* ── Stage steps ── */}
          <ol className="mt-5 space-y-0">
            {STAGES.map((s, i) => {
              const done   = i < stageIdx || isDone;
              const active = i === stageIdx && !isDone && !isError;
              const err    = isError && i === stageIdx;
              const future = !done && !active && !err;

              return (
                <li
                  key={s.key}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-500"
                  style={{
                    background: active
                      ? "rgba(59,130,246,0.08)"
                      : "transparent",
                    borderLeft: active
                      ? "2px solid #3b82f6"
                      : "2px solid transparent",
                  }}
                >
                  {/* Icon */}
                  <div className="shrink-0 w-5 h-5 flex items-center justify-center">
                    {err    ? <AlertCircle className="w-5 h-5 text-destructive" />
                    : done  ? <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    : active ? (
                      /* Dual-ring spinner */
                      <span
                        style={{
                          display: "inline-block",
                          width: 18, height: 18,
                          border: "2.5px solid rgba(96,165,250,0.25)",
                          borderTopColor: "#60a5fa",
                          borderRadius: "50%",
                          animation: "spin 0.75s linear infinite",
                        }}
                      />
                    )
                    : <div className="w-4 h-4 rounded-full border-2 border-muted-foreground/20" />}
                  </div>

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <span
                      className="text-sm font-medium transition-colors duration-300"
                      style={{
                        color: active ? "#f1f5f9"
                          : done  ? "#64748b"
                          : "#374151",
                        textDecoration: done ? "line-through" : "none",
                        opacity: future ? 0.45 : 1,
                      }}
                    >
                      {s.label}
                    </span>
                    {active && lastMessage && (
                      <p className="text-xs text-blue-400/80 mt-0.5 truncate">{lastMessage}</p>
                    )}
                  </div>

                  {/* Right: timing indicator for active */}
                  {active && (
                    <span className="text-xs text-blue-400/60 shrink-0 tabular-nums">
                      {pct}%
                    </span>
                  )}
                  {done && (
                    <span className="text-xs text-emerald-500/60 shrink-0">✓</span>
                  )}
                </li>
              );
            })}
          </ol>

          {/* Error */}
          {job?.error && (
            <div className="mt-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md p-3">
              {job.error}
            </div>
          )}

          {/* Event log */}
          <div className="mt-5 max-h-36 overflow-auto text-xs font-mono text-muted-foreground bg-muted/40 rounded-md p-3 border border-border/60">
            {events.length === 0
              ? <span className="text-muted-foreground/40 animate-pulse">Connecting to pipeline…</span>
              : events.slice(-20).map((e, i) => (
                  <div key={i}>
                    <span className="text-blue-400/70">[{e.stage}]</span> {e.message}
                  </div>
                ))
            }
          </div>
        </CardContent>
      </Card>

      {/* Keyframe styles injected inline */}
      <style>{`
        @keyframes shimmer {
          0%   { left: -60%; }
          100% { left: 110%; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
