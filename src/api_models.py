"""FastAPI request/response Pydantic models for the /summarize endpoint.

The service ALWAYS returns 200 with a structured response — n8n branches
on the `status` field rather than HTTP status codes. This keeps webhook
integrations robust and prevents n8n from retrying on non-200.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    source_url: str | None = Field(
        default=None,
        description="Landing page URL for the report (e.g. chase.com/...).",
    )
    pdf_base64: str | None = Field(
        default=None,
        description="Base64-encoded PDF bytes. If provided, skips Playwright download.",
    )
    email_subject: str | None = Field(
        default=None,
        description="Subject of the forwarded email (used for report title hint).",
    )
    sender: str | None = Field(
        default=None,
        description="Email sender address (for audit).",
    )
    message_id: str | None = Field(
        default=None,
        description="Unique email Message-ID header, used for idempotency.",
    )


class SummarizeResponse(BaseModel):
    status: str = Field(
        ...,
        description="'success' | 'failed' | 'duplicate'",
    )
    summary_markdown: str | None = None
    summary_html: str | None = None
    audit_id: str
    source_pdf_hash: str | None = None
    page_count: int | None = None
    response_time_ms: int = 0
    error: str | None = None
