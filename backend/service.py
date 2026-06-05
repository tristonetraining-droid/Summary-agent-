"""FastAPI service exposing the CIMSummarizer pipeline + editable summaries."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from src import config
from src.assembler import assemble
from src.jobs import registry
from src.models import CIMSummary, JobStage
from src.pdf_export import docx_to_pdf

try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False

_supabase: Optional[object] = None


def _get_supabase():
    global _supabase
    if not _SUPABASE_AVAILABLE:
        raise HTTPException(503, "supabase package not installed")
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise HTTPException(503, "Supabase not configured — set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    if _supabase is None:
        _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("cimsummarizer")

app = FastAPI(title="CIMSummarizer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "jobs_dir": str(config.JOBS_DIR)}


@app.post("/api/jobs")
async def create_job(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    deal_name: str = Form(...),
    sponsor_name: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload must be a PDF")

    state = registry.create(
        filename=file.filename,
        deal_name=deal_name,
        sponsor_name=sponsor_name,
    )
    dest = registry.upload_path(state.id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)

    # Schedule pipeline (start immediately in the running loop)
    asyncio.create_task(registry.run(state.id))
    return {"id": state.id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    state = registry.get(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    return JSONResponse(json.loads(state.model_dump_json()))


@app.get("/api/jobs/{job_id}/events")
async def stream_events(job_id: str):
    state = registry.get(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    q = registry.queue(job_id)

    async def gen():
        # Send the historical events first
        for ev in state.events:
            yield {"event": "stage", "data": ev.model_dump_json()}
        # Then stream live
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": "stage", "data": json.dumps(data)}
            if data.get("stage") in ("done", "error"):
                break

    return EventSourceResponse(gen())


@app.put("/api/jobs/{job_id}/summary")
async def update_summary(job_id: str, summary: CIMSummary):
    state = registry.get(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    registry.save_summary(job_id, summary)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/cim-page/{n}.png")
async def get_page(job_id: str, n: int):
    f = registry.job_dir(job_id) / "pages" / f"page-{n}.png"
    if not f.exists():
        raise HTTPException(404, "Page not found")
    return FileResponse(str(f), media_type="image/png")


@app.post("/api/jobs/{job_id}/export")
async def export(job_id: str, format: str = "docx"):
    state = registry.get(job_id)
    if not state or not state.summary:
        raise HTTPException(404, "Job not ready")

    # Resolve image_paths from page numbers selected in UI
    sel = state.summary.product_offering.image_page_numbers
    pages_dir = registry.job_dir(job_id) / "pages"
    state.summary.product_offering.image_paths = [
        str(pages_dir / f"page-{p}.png") for p in sel
        if (pages_dir / f"page-{p}.png").exists()
    ]

    safe = "".join(c for c in state.deal_name if c.isalnum() or c in ("-", "_")) or "Deal"
    docx_path = registry.job_dir(job_id) / f"CIM_Summary_{safe}.docx"
    assemble(state.summary, docx_path)

    if format == "docx":
        return FileResponse(
            str(docx_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=docx_path.name,
        )
    if format == "pdf":
        pdf_path = docx_to_pdf(docx_path, registry.job_dir(job_id))
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)
    raise HTTPException(400, "format must be docx or pdf")


@app.post("/api/jobs/{job_id}/save-to-history")
async def save_to_history(job_id: str):
    state = registry.get(job_id)
    if not state or not state.summary:
        raise HTTPException(404, "Job not ready or has no summary")
    sb = _get_supabase()
    payload = {
        "job_id": job_id,
        "deal_name": state.deal_name,
        "sponsor_name": state.sponsor_name,
        "summary": json.loads(state.summary.model_dump_json()),
    }
    result = sb.table("saved_summaries").insert(payload).execute()
    if not result.data:
        raise HTTPException(500, "Supabase insert returned no data")
    return result.data[0]


@app.get("/api/summaries")
async def list_saved_summaries():
    sb = _get_supabase()
    result = (
        sb.table("saved_summaries")
        .select("id,job_id,deal_name,sponsor_name,saved_at")
        .order("saved_at", desc=True)
        .execute()
    )
    return result.data or []


@app.get("/api/summaries/{summary_id}")
async def get_saved_summary(summary_id: str):
    sb = _get_supabase()
    result = (
        sb.table("saved_summaries")
        .select("*")
        .eq("id", summary_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Saved summary not found")
    return result.data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8000, reload=True)
