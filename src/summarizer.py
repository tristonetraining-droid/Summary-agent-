"""Map-reduce summarization with Claude using structured tool-use output.

MAP:    each section -> SectionSummary (grounded facts only)
REDUCE: list[SectionSummary] -> ExecutiveSummary (one-page CEO brief)

Structured output is enforced via Anthropic's tool-use API: we declare a
single tool whose input_schema matches our Pydantic model, then force the
model to call it. This guarantees we receive a JSON object we can validate
with Pydantic — no regex parsing of free text.
"""
from __future__ import annotations

import json
import time
from typing import Any

from anthropic import Anthropic, APIError, RateLimitError
from pydantic import ValidationError

from .config import (
    MAX_SECTION_TOKENS,
    MAX_SUMMARY_TOKENS,
    MODEL_NAME,
    require_api_key,
)
from .models import ExecutiveSummary, SectionSummary


# ---------------------------------------------------------------------------
# Tool schemas (mirror the Pydantic models)
# ---------------------------------------------------------------------------
SECTION_TOOL: dict[str, Any] = {
    "name": "record_section_summary",
    "description": (
        "Record a grounded summary of one section of an institutional "
        "research report. Use ONLY facts that appear in the provided text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "section_title": {"type": "string"},
            "summary": {
                "type": "string",
                "description": (
                    "Concise, dense summary of the section. Institutional "
                    "tone. No filler. Numbers must come from the text."
                ),
            },
            "key_figures": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Specific figures/claims that appear verbatim in the "
                    "section (e.g. 'S&P 500 target 6,000', 'CPI 2.4% YoY')."
                ),
            },
            "source_pages": {
                "type": "string",
                "description": "Approximate page range, e.g. '12-18'.",
            },
        },
        "required": ["section_title", "summary", "key_figures", "source_pages"],
    },
}

EXEC_TOOL: dict[str, Any] = {
    "name": "record_executive_summary",
    "description": (
        "Record the final one-page executive summary for the CEO. Every "
        "figure must trace to the provided section summaries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "report_title": {"type": "string"},
            "source": {"type": "string"},
            "report_date": {"type": "string"},
            "page_count": {"type": "integer"},
            "headline_takeaway": {
                "type": "string",
                "description": (
                    "The single most important insight of the report. Not a "
                    "generic intro; the thing the CEO most needs to know."
                ),
            },
            "key_findings": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
                "description": "3-5 dense, numbers-driven bullets.",
            },
            "market_implications": {
                "type": "string",
                "description": "2-3 sentences on what this means for markets/positioning.",
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 4,
            },
            "bottom_line": {
                "type": "string",
                "description": "1-2 sentence recommendation.",
            },
            "confidence_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anything the model was unsure about; empty if none.",
            },
        },
        "required": [
            "report_title",
            "source",
            "report_date",
            "page_count",
            "headline_takeaway",
            "key_findings",
            "market_implications",
            "risks",
            "bottom_line",
            "confidence_notes",
        ],
    },
}


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=require_api_key())
    return _client


# ---------------------------------------------------------------------------
# Retry logic for rate limits
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 5
INITIAL_BACKOFF: float = 30.0  # seconds — generous for 10k TPM limits


def _call_with_retry(fn, *args, **kwargs) -> Any:
    """Call `fn(*args, **kwargs)` with exponential backoff on 429 errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except RateLimitError as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = INITIAL_BACKOFF * (2 ** attempt)
            time.sleep(wait)
        except APIError:
            raise
    # Should not reach here, but satisfy type checker.
    raise RuntimeError("Retry loop exhausted unexpectedly.")


def _extract_tool_input(message: Any, tool_name: str) -> dict[str, Any]:
    """Pull the structured tool_use input out of an Anthropic Message."""
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            data = block.input
            if isinstance(data, str):
                data = json.loads(data)
            return dict(data)
    raise RuntimeError(
        f"Claude did not return a tool_use block for {tool_name!r}. "
        f"stop_reason={getattr(message, 'stop_reason', None)!r}"
    )


# ---------------------------------------------------------------------------
# MAP
# ---------------------------------------------------------------------------
SECTION_SYSTEM_PROMPT = (
    "You are summarizing a single section of an institutional research "
    "report (typically J.P. Morgan Wealth Management) for an investment "
    "research firm's CEO.\n\n"
    "RULES:\n"
    "1. GROUNDING: Use ONLY information that appears in the provided text. "
    "Do not invent numbers, dates, tickers, or claims. If a figure is not "
    "in the text, do not include it.\n"
    "2. PRECISION: Preserve specific figures verbatim — percentages, price "
    "targets, dollar amounts, basis points, dates.\n"
    "3. TONE: Institutional analyst. Dense, no filler, no 'this section "
    "discusses' padding.\n"
    "4. STRUCTURE: Always respond by calling the record_section_summary "
    "tool. Never reply in free text."
)


def summarize_section(section: dict[str, Any]) -> SectionSummary:
    """MAP: produce a grounded summary for one section."""
    title = section.get("title", "Untitled")
    pages = section.get("approx_pages", "")
    body = section.get("text", "")

    user_msg = (
        f"SECTION TITLE: {title}\n"
        f"APPROX PAGES: {pages or 'unknown'}\n"
        f"---\n{body}\n---\n"
        "Call record_section_summary now with a grounded summary of this section."
    )

    try:
        msg = _call_with_retry(
            _get_client().messages.create,
            model=MODEL_NAME,
            max_tokens=MAX_SECTION_TOKENS,
            system=SECTION_SYSTEM_PROMPT,
            tools=[SECTION_TOOL],
            tool_choice={"type": "tool", "name": "record_section_summary"},
            messages=[{"role": "user", "content": user_msg}],
        )
    except (APIError, RateLimitError) as exc:
        raise RuntimeError(f"Claude MAP call failed for section {title!r}: {exc}") from exc

    raw = _extract_tool_input(msg, "record_section_summary")
    # Backfill page range from our parser if the model omitted it.
    if not raw.get("source_pages") and pages:
        raw["source_pages"] = pages
    if not raw.get("section_title"):
        raw["section_title"] = title

    try:
        return SectionSummary.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(
            f"Claude returned a SectionSummary that failed validation: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# REDUCE
# ---------------------------------------------------------------------------
EXEC_SYSTEM_PROMPT = (
    "You are briefing the CEO of Tristone Strategic Partners, an investment "
    "research firm. Produce a dense, one-page executive summary of an "
    "institutional research report.\n\n"
    "RULES:\n"
    "1. GROUNDING: Every figure or claim MUST come from the provided "
    "section summaries. Do not invent anything. If the section summaries "
    "do not support a claim, omit it.\n"
    "2. HEADLINE: The headline_takeaway is the SINGLE most important "
    "insight — not a generic intro like 'this report covers...'.\n"
    "3. KEY FINDINGS: 3-5 bullets, each with real numbers from the source.\n"
    "4. TONE: Senior institutional analyst. Precise, numbers-driven, no "
    "hedging filler, no AI tells.\n"
    "5. CONFIDENCE: If the section summaries leave something ambiguous, "
    "note it in confidence_notes rather than guessing.\n"
    "6. STRUCTURE: Always respond by calling the record_executive_summary "
    "tool. Never reply in free text."
)


def synthesize_summary(
    section_summaries: list[SectionSummary],
    metadata: dict[str, Any],
) -> ExecutiveSummary:
    """REDUCE: synthesize all section summaries into the final one-pager."""
    if not section_summaries:
        raise ValueError("Cannot synthesize summary from zero sections.")

    payload = {
        "metadata": {
            "report_title_hint": metadata.get("report_title", ""),
            "source_hint": metadata.get("source", "J.P. Morgan Wealth Management"),
            "report_date_hint": metadata.get("report_date", ""),
            "page_count": metadata.get("page_count", 0),
            "source_url": metadata.get("source_url", ""),
        },
        "sections": [s.model_dump() for s in section_summaries],
    }

    user_msg = (
        "Below are grounded section summaries from a single institutional "
        "research report, plus metadata. Synthesize them into a one-page "
        "executive summary by calling record_executive_summary. Use ONLY "
        "facts from the section summaries.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    try:
        msg = _call_with_retry(
            _get_client().messages.create,
            model=MODEL_NAME,
            max_tokens=MAX_SUMMARY_TOKENS,
            system=EXEC_SYSTEM_PROMPT,
            tools=[EXEC_TOOL],
            tool_choice={"type": "tool", "name": "record_executive_summary"},
            messages=[{"role": "user", "content": user_msg}],
        )
    except (APIError, RateLimitError) as exc:
        raise RuntimeError(f"Claude REDUCE call failed: {exc}") from exc

    raw = _extract_tool_input(msg, "record_executive_summary")

    # Backfill known metadata if the model left fields empty.
    raw.setdefault("page_count", metadata.get("page_count", 0))
    if not raw.get("source"):
        raw["source"] = metadata.get("source", "J.P. Morgan Wealth Management")
    if not raw.get("report_title"):
        raw["report_title"] = metadata.get("report_title", "Untitled Report")
    if not raw.get("report_date"):
        raw["report_date"] = metadata.get("report_date", "Unknown")

    try:
        return ExecutiveSummary.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(
            f"Claude returned an ExecutiveSummary that failed validation: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def format_summary(exec_summary: ExecutiveSummary) -> str:
    """Render an ExecutiveSummary as clean one-page markdown."""
    lines: list[str] = []
    lines.append(f"# {exec_summary.report_title}")
    lines.append("")
    lines.append(
        f"**Source:** {exec_summary.source}  "
        f"**Date:** {exec_summary.report_date}  "
        f"**Pages:** {exec_summary.page_count}"
    )
    lines.append("")
    lines.append("## Headline Takeaway")
    lines.append(exec_summary.headline_takeaway)
    lines.append("")
    lines.append("## Key Findings")
    for kf in exec_summary.key_findings:
        lines.append(f"- {kf}")
    lines.append("")
    lines.append("## Market Implications")
    lines.append(exec_summary.market_implications)
    lines.append("")
    lines.append("## Risks")
    for r in exec_summary.risks:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Bottom Line")
    lines.append(exec_summary.bottom_line)
    if exec_summary.confidence_notes:
        lines.append("")
        lines.append("## Confidence Notes")
        for n in exec_summary.confidence_notes:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)
