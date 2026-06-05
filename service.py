"""BriefForge FastAPI service — Day 2 deployment entry point.

Endpoints:
    POST /summarize  — accepts a URL (or base64 PDF), runs the full pipeline,
                       returns structured JSON with the executive summary.
    GET  /health     — 200 OK for Railway health checks.

Design:
    - ALWAYS returns HTTP 200 with a status field so n8n can branch cleanly.
    - Idempotency via message_id: duplicate requests return the cached result.
    - Each pipeline stage is wrapped in try/except; failures populate the
      `error` field rather than raising.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib
from fastapi import FastAPI

from src.api_models import SummarizeRequest, SummarizeResponse
from src.config import MODEL_NAME, OUTPUT_DIR, SAMPLES_DIR
from src.downloader import download_report
from src.models import AuditRecord
from src.parser import compute_hash, extract_text, get_page_count, split_into_sections
from src.summarizer import format_summary, summarize_section, synthesize_summary

app = FastAPI(
    title="BriefForge",
    description="Autonomous research-report summarization service for Tristone Strategic Partners.",
    version="0.2.0",
)


@app.on_event("startup")
def _startup():
    """Run DB migration on startup (no-op if table already exists)."""
    try:
        from src.db import init_db
        init_db()
    except Exception:
        pass  # DB unavailable — service still starts; audit falls back to JSON.

# ---------------------------------------------------------------------------
# In-memory idempotency store (Day 1 fallback; Phase 2 upgrades to Postgres)
# ---------------------------------------------------------------------------
_processed: dict[str, SummarizeResponse] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _render_html(markdown_text: str) -> str:
    """Convert markdown summary to HTML suitable for email body."""
    return md_lib.markdown(markdown_text, extensions=["tables", "fenced_code"])


def _save_base64_pdf(data: str) -> str:
    """Decode base64 PDF and save to samples/. Returns path."""
    try:
        blob = base64.b64decode(data)
    except Exception as exc:
        raise ValueError(f"Invalid base64 PDF data: {exc}") from exc
    if not blob[:5] == b"%PDF-":
        raise ValueError("Decoded bytes are not a valid PDF (missing %PDF- header).")
    digest = hashlib.sha256(blob).hexdigest()[:12]
    dest = SAMPLES_DIR / f"uploaded-{digest}.pdf"
    dest.write_bytes(blob)
    return str(dest.resolve())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    from src.db import health_check
    db_ok = False
    try:
        db_ok = health_check()
    except Exception:
        pass
    return {"status": "ok", "db": "connected" if db_ok else "unavailable"}


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest):
    start_ms = int(time.time() * 1000)
    run_id = uuid.uuid4().hex[:12]

    # --- Idempotency check (Postgres primary, in-memory fallback) ---
    if req.message_id:
        # Fast path: in-memory cache (avoids DB round-trip on warm instances).
        if req.message_id in _processed:
            cached = _processed[req.message_id]
            return SummarizeResponse(
                status="duplicate",
                summary_markdown=cached.summary_markdown,
                summary_html=cached.summary_html,
                audit_id=cached.audit_id,
                source_pdf_hash=cached.source_pdf_hash,
                page_count=cached.page_count,
                response_time_ms=0,
                error=None,
            )
        # Durable path: check Postgres (survives restarts).
        try:
            from src.db import find_by_message_id
            existing = find_by_message_id(req.message_id)
            if existing and existing.get("status") == "success":
                return SummarizeResponse(
                    status="duplicate",
                    summary_markdown=existing.get("summary_markdown"),
                    summary_html=_render_html(existing.get("summary_markdown") or ""),
                    audit_id=existing["run_id"],
                    source_pdf_hash=existing.get("pdf_hash"),
                    page_count=existing.get("page_count"),
                    response_time_ms=0,
                    error=None,
                )
        except Exception:
            pass  # DB unavailable — continue to process normally.

    # --- Validate input ---
    if not req.source_url and not req.pdf_base64:
        elapsed = int(time.time() * 1000) - start_ms
        resp = SummarizeResponse(
            status="failed",
            audit_id=run_id,
            response_time_ms=elapsed,
            error="Must provide either source_url or pdf_base64.",
        )
        _log_audit_json(run_id, req, resp, elapsed)
        return resp

    # --- Stage 1: Get PDF ---
    pdf_path: str | None = None
    try:
        if req.pdf_base64:
            pdf_path = _save_base64_pdf(req.pdf_base64)
        else:
            pdf_path = download_report(req.source_url)
    except Exception as exc:
        elapsed = int(time.time() * 1000) - start_ms
        resp = SummarizeResponse(
            status="failed",
            audit_id=run_id,
            response_time_ms=elapsed,
            error=f"Download failed: {exc}",
        )
        _log_audit_json(run_id, req, resp, elapsed)
        return resp

    # --- Stage 2: Parse ---
    try:
        pdf_hash = compute_hash(pdf_path)
        page_count = get_page_count(pdf_path)
        text, offsets = extract_text(pdf_path)
        sections = split_into_sections(text, offsets)
        if not sections:
            raise RuntimeError("No sections extracted from PDF.")
    except Exception as exc:
        elapsed = int(time.time() * 1000) - start_ms
        resp = SummarizeResponse(
            status="failed",
            audit_id=run_id,
            source_pdf_hash=pdf_hash if "pdf_hash" in dir() else None,
            page_count=page_count if "page_count" in dir() else None,
            response_time_ms=elapsed,
            error=f"Parse failed: {exc}",
        )
        _log_audit_json(run_id, req, resp, elapsed)
        return resp

    # --- Stage 3: MAP ---
    section_summaries = []
    try:
        for sec in sections:
            section_summaries.append(summarize_section(sec))
    except Exception as exc:
        elapsed = int(time.time() * 1000) - start_ms
        resp = SummarizeResponse(
            status="failed",
            audit_id=run_id,
            source_pdf_hash=pdf_hash,
            page_count=page_count,
            response_time_ms=elapsed,
            error=f"MAP summarization failed: {exc}",
        )
        _log_audit_json(run_id, req, resp, elapsed)
        return resp

    # --- Stage 4: REDUCE ---
    try:
        metadata = {
            "report_title": req.email_subject or Path(pdf_path).stem.replace("-", " ").title(),
            "source": "J.P. Morgan Wealth Management",
            "report_date": "",
            "page_count": page_count,
            "source_url": req.source_url or "",
        }
        exec_summary = synthesize_summary(section_summaries, metadata)
    except Exception as exc:
        elapsed = int(time.time() * 1000) - start_ms
        resp = SummarizeResponse(
            status="failed",
            audit_id=run_id,
            source_pdf_hash=pdf_hash,
            page_count=page_count,
            response_time_ms=elapsed,
            error=f"REDUCE synthesis failed: {exc}",
        )
        _log_audit_json(run_id, req, resp, elapsed)
        return resp

    # --- Stage 5: Format + respond ---
    summary_md = format_summary(exec_summary)
    summary_html = _render_html(summary_md)
    elapsed = int(time.time() * 1000) - start_ms

    resp = SummarizeResponse(
        status="success",
        summary_markdown=summary_md,
        summary_html=summary_html,
        audit_id=run_id,
        source_pdf_hash=pdf_hash,
        page_count=page_count,
        response_time_ms=elapsed,
    )

    # Cache for idempotency
    if req.message_id:
        _processed[req.message_id] = resp

    # Audit — write to Postgres (with JSON fallback handled inside log_run)
    _log_audit_full(run_id, req, resp, elapsed)

    return resp


# ---------------------------------------------------------------------------
# Audit — Postgres primary + JSON fallback (via updated src/audit.py)
# ---------------------------------------------------------------------------
def _log_audit_full(
    run_id: str,
    req: SummarizeRequest,
    resp: SummarizeResponse,
    elapsed_ms: int,
) -> None:
    """Best-effort audit write. Postgres first, JSON fallback."""
    try:
        from src.db import DBUnavailableError, write_audit
        write_audit({
            "run_id": run_id,
            "message_id": req.message_id,
            "source_url": req.source_url or "",
            "pdf_hash": resp.source_pdf_hash or "",
            "page_count": resp.page_count or 0,
            "model": MODEL_NAME,
            "sender": req.sender,
            "recipient": None,
            "email_subject": req.email_subject,
            "output_path": "",
            "summary_markdown": resp.summary_markdown,
            "response_time_ms": elapsed_ms,
            "status": resp.status if resp.status != "failed" else f"failed: {resp.error}",
            "error": resp.error,
        })
    except Exception:
        pass  # Fall through to JSON

    # Always also write JSON (local visibility + Day 1 pipeline compat)
    try:
        from src.audit import log_run
        record = AuditRecord(
            run_id=run_id,
            source_url=req.source_url or "",
            pdf_hash=resp.source_pdf_hash or "",
            timestamp=_now_iso(),
            model=MODEL_NAME,
            page_count=resp.page_count or 0,
            output_path="",
            status=resp.status if resp.status != "failed" else f"failed: {resp.error}",
        )
        from src.audit import _write_json
        _write_json(record)
    except Exception:
        pass  # Audit must never crash the service
