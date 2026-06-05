-- BriefForge audit log schema
-- Append-only. Never UPDATE or DELETE rows (SOC 2 / ISO 27001 requirement).

CREATE TABLE IF NOT EXISTS audit_log (
    run_id            TEXT        PRIMARY KEY,
    message_id        TEXT        UNIQUE,          -- email Message-ID for idempotency
    source_url        TEXT,
    pdf_hash          TEXT,
    page_count        INT,
    model             TEXT,
    sender            TEXT,
    recipient         TEXT,
    email_subject     TEXT,
    output_path       TEXT,
    summary_markdown  TEXT,
    response_time_ms  INT,
    status            TEXT        NOT NULL,
    error             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_message_id  ON audit_log(message_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at  ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_status      ON audit_log(status);
