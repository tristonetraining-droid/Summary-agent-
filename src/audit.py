"""Audit logging — Postgres primary, JSON fallback.

Write path (in order):
  1. Postgres via src/db.py  (durable, survives restarts, idempotency-safe)
  2. JSON file fallback       (used when DATABASE_URL is unset or DB unreachable)

The JSON fallback keeps Day 1 local-pipeline behaviour intact.
Never raises — audit must not crash the pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import AUDIT_LOG_PATH
from .models import AuditRecord


def log_run(record: AuditRecord, path: Path | None = None) -> Path:
    """Persist `record` to Postgres (primary) or JSON file (fallback).

    Always returns the JSON path regardless of which backend was used,
    so callers (including pipeline.py) have a stable return value.
    """
    # --- Primary: Postgres ---
    try:
        from .db import DBUnavailableError, write_audit
        pg_record = record.model_dump()
        write_audit(pg_record)
        # Also write JSON as secondary record for local visibility.
        _write_json(record, path)
        return path or AUDIT_LOG_PATH
    except Exception:
        # DB unavailable or not configured — fall through to JSON-only.
        pass

    # --- Fallback: JSON ---
    _write_json(record, path)
    return path or AUDIT_LOG_PATH


def _write_json(record: AuditRecord, path: Path | None = None) -> None:
    """Append-only write to the local JSON audit file."""
    log_path = Path(path) if path else AUDIT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if log_path.exists() and log_path.stat().st_size > 0:
        try:
            with log_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    existing = loaded
        except json.JSONDecodeError:
            backup = log_path.with_suffix(log_path.suffix + ".corrupt")
            log_path.replace(backup)
            existing = []

    existing.append(record.model_dump())

    tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    tmp.replace(log_path)
