"""Postgres connection layer for BriefForge.

Uses a simple connection pool via psycopg2. Supabase (and Railway Postgres)
are standard Postgres — no special driver needed.

Fallback policy: if the DB is unreachable at any point, functions raise
`DBUnavailableError`. The audit layer catches this and falls back to JSON.
This means the pipeline NEVER fails because of a DB issue.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

from .config import ROOT_DIR


class DBUnavailableError(RuntimeError):
    """Raised when Postgres cannot be reached or queried."""


# ---------------------------------------------------------------------------
# Connection pool (lazy init)
# ---------------------------------------------------------------------------
_pool: psycopg2.pool.SimpleConnectionPool | None = None

_MIGRATION_PATH = ROOT_DIR / "migrations" / "001_initial.sql"


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise DBUnavailableError(
            "DATABASE_URL is not set. Postgres audit unavailable."
        )
    try:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=dsn,
            connect_timeout=5,
            sslmode="require",  # Supabase requires SSL
        )
        return _pool
    except psycopg2.OperationalError as exc:
        raise DBUnavailableError(f"Cannot connect to Postgres: {exc}") from exc


def _conn():
    """Context manager: get a connection from the pool, return on exit."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        pool = _get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    return _ctx()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Run the migration SQL if the table doesn't exist yet.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    sql = _MIGRATION_PATH.read_text(encoding="utf-8")
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    except DBUnavailableError:
        raise
    except psycopg2.Error as exc:
        raise DBUnavailableError(f"Migration failed: {exc}") from exc


def find_by_message_id(message_id: str) -> dict[str, Any] | None:
    """Return the audit row for `message_id`, or None if not found."""
    if not message_id:
        return None
    try:
        with _conn() as conn:
            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(
                    "SELECT * FROM audit_log WHERE message_id = %s LIMIT 1",
                    (message_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except DBUnavailableError:
        raise
    except psycopg2.Error as exc:
        raise DBUnavailableError(f"DB query failed: {exc}") from exc


def write_audit(record: dict[str, Any]) -> None:
    """Insert one audit record. Silently ignores duplicate run_id conflicts."""
    cols = [
        "run_id", "message_id", "source_url", "pdf_hash", "page_count",
        "model", "sender", "recipient", "email_subject", "output_path",
        "summary_markdown", "response_time_ms", "status", "error",
    ]
    values = {c: record.get(c) for c in cols}

    placeholders = ", ".join(f"%({c})s" for c in cols)
    col_list = ", ".join(cols)

    sql = (
        f"INSERT INTO audit_log ({col_list}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (run_id) DO NOTHING"
    )
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
    except DBUnavailableError:
        raise
    except psycopg2.Error as exc:
        raise DBUnavailableError(f"DB write failed: {exc}") from exc


def health_check() -> bool:
    """Return True if Postgres is reachable. Used by /health endpoint."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False
