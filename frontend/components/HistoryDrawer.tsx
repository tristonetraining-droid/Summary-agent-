"use client";
import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { History, X, ChevronRight, Clock, Building2, Loader2, AlertCircle } from "lucide-react";
import { listHistory } from "@/lib/api";
import type { SavedSummaryMeta } from "@/lib/types";

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function HistoryDrawer() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<SavedSummaryMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listHistory();
      setItems(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  function openSummary(id: string) {
    setOpen(false);
    router.push(`/history/${id}`);
  }

  const drawerPanel = (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 99999 }}
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.55)" }} />

      {/* Panel */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: 0, right: 0, bottom: 0,
          width: 340,
          display: "flex",
          flexDirection: "column",
          background: "#0f1117",
          borderLeft: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "-12px 0 40px rgba(0,0,0,0.6)",
          color: "#f1f5f9",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 18px", borderBottom: "1px solid rgba(255,255,255,0.08)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <History size={15} style={{ opacity: 0.6 }} />
            <span style={{ fontWeight: 600, fontSize: 14 }}>Saved Summaries</span>
            {items.length > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, background: "rgba(255,255,255,0.12)", borderRadius: 999, padding: "2px 8px" }}>
                {items.length}
              </span>
            )}
          </div>
          <button onClick={() => setOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94a3b8", padding: 4, display: "flex" }}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "48px 16px", color: "#94a3b8", fontSize: 14 }}>
              <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Loading…
            </div>
          )}
          {!loading && error && (
            <div style={{ margin: 12, padding: 12, borderRadius: 8, background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", color: "#fca5a5", fontSize: 13, display: "flex", gap: 8 }}>
              <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} /> {error}
            </div>
          )}
          {!loading && !error && items.length === 0 && (
            <div style={{ textAlign: "center", padding: "60px 24px", color: "#64748b" }}>
              <History size={30} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
              <p style={{ fontSize: 14, margin: "0 0 6px" }}>No saved summaries yet.</p>
              <p style={{ fontSize: 12, opacity: 0.6, margin: 0 }}>Use &ldquo;Save to History&rdquo; on the edit page.</p>
            </div>
          )}
          {!loading && !error && items.map((item, idx) => (
            <div
              key={item.id}
              onClick={() => openSummary(item.id)}
              style={{
                padding: "14px 18px",
                cursor: "pointer",
                borderBottom: idx < items.length - 1 ? "1px solid rgba(255,255,255,0.06)" : "none",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.deal_name}
                  </p>
                  {item.sponsor_name && (
                    <p style={{ fontSize: 12, color: "#94a3b8", margin: "3px 0 0", display: "flex", alignItems: "center", gap: 4 }}>
                      <Building2 size={11} style={{ flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.sponsor_name}</span>
                    </p>
                  )}
                  <p style={{ fontSize: 11, color: "#64748b", margin: "4px 0 0", display: "flex", alignItems: "center", gap: 4 }}>
                    <Clock size={10} style={{ flexShrink: 0 }} />
                    {formatDate(item.saved_at)}
                  </p>
                </div>
                <ChevronRight size={14} style={{ color: "#475569", flexShrink: 0, marginTop: 3 }} />
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 18px", borderTop: "1px solid rgba(255,255,255,0.08)", flexShrink: 0 }}>
          <span style={{ fontSize: 11, color: "#475569" }}>{items.length > 0 ? `${items.length} saved` : ""}</span>
          <button onClick={load} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 12, color: "#64748b", padding: 0 }}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-md hover:bg-muted"
      >
        <History className="w-4 h-4" />
        <span className="hidden sm:inline">History</span>
        {items.length > 0 && (
          <span className="ml-0.5 text-xs bg-foreground/10 rounded-full px-1.5">{items.length}</span>
        )}
      </button>
      {mounted && open && createPortal(drawerPanel, document.body)}
    </>
  );
}
