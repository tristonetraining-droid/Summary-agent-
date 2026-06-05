"""In-memory + on-disk job registry."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from . import config
from .models import CIMSummary, JobStage, JobState, StageEvent
from .pipeline_core import run_pipeline


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    def _path(self, job_id: str) -> Path:
        return config.JOBS_DIR / job_id

    def _state_file(self, job_id: str) -> Path:
        return self._path(job_id) / "state.json"

    def _persist(self, state: JobState) -> None:
        f = self._state_file(state.id)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def _load(self, job_id: str) -> Optional[JobState]:
        f = self._state_file(job_id)
        if not f.exists():
            return None
        try:
            return JobState.model_validate_json(f.read_text(encoding="utf-8"))
        except Exception:
            return None

    def create(self, *, filename: str, deal_name: str, sponsor_name: str) -> JobState:
        jid = uuid.uuid4().hex[:12]
        now = time.time()
        state = JobState(
            id=jid,
            filename=filename,
            deal_name=deal_name,
            sponsor_name=sponsor_name,
            stage=JobStage.QUEUED,
            created_at=now,
            updated_at=now,
        )
        self._path(jid).mkdir(parents=True, exist_ok=True)
        self._jobs[jid] = state
        self._queues[jid] = asyncio.Queue()
        self._persist(state)
        return state

    def get(self, job_id: str) -> Optional[JobState]:
        if job_id in self._jobs:
            return self._jobs[job_id]
        loaded = self._load(job_id)
        if loaded:
            self._jobs[job_id] = loaded
        return loaded

    def update(self, job_id: str, **fields) -> Optional[JobState]:
        state = self.get(job_id)
        if not state:
            return None
        for k, v in fields.items():
            setattr(state, k, v)
        state.updated_at = time.time()
        self._persist(state)
        return state

    def queue(self, job_id: str) -> asyncio.Queue:
        return self._queues.setdefault(job_id, asyncio.Queue())

    def save_summary(self, job_id: str, summary: CIMSummary) -> Optional[JobState]:
        return self.update(job_id, summary=summary)

    def upload_path(self, job_id: str) -> Path:
        return self._path(job_id) / "input.pdf"

    def job_dir(self, job_id: str) -> Path:
        return self._path(job_id)

    async def run(self, job_id: str) -> None:
        state = self.get(job_id)
        if not state:
            return
        loop = asyncio.get_running_loop()
        q = self.queue(job_id)

        def on_progress(stage: JobStage, msg: str, prog: float) -> None:
            evt = StageEvent(stage=stage, message=msg, progress=prog, ts=time.time())
            state.events.append(evt)
            state.stage = stage
            state.updated_at = time.time()
            self._persist(state)
            # Push to SSE queue from worker thread
            asyncio.run_coroutine_threadsafe(q.put(evt.model_dump()), loop)

        try:
            summary, docx_path, _pages = await loop.run_in_executor(
                None,
                lambda: run_pipeline(
                    pdf_path=self.upload_path(job_id),
                    job_dir=self.job_dir(job_id),
                    deal_name=state.deal_name,
                    sponsor_name=state.sponsor_name,
                    on_progress=on_progress,
                ),
            )
            state.summary = summary
            state.stage = JobStage.DONE
            state.page_count = max((e.progress for e in state.events), default=0) and 0
            self._persist(state)
            await q.put({"stage": "done", "message": "done", "progress": 1.0, "ts": time.time()})
        except Exception as e:
            state.error = str(e)
            state.stage = JobStage.ERROR
            self._persist(state)
            await q.put({"stage": "error", "message": str(e), "progress": 0.0, "ts": time.time()})


registry = JobRegistry()
