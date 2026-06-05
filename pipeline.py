"""BriefForge Day-1 entry point.

Usage:
    python pipeline.py <landing_page_url>

Stages:
    1. Download report PDF via Playwright (handles click-to-download and
       new-tab navigation).
    2. Hash + page-count + text extraction.
    3. Split into sections.
    4. MAP: per-section summaries via Claude (structured tool use).
    5. REDUCE: synthesize one-page executive summary.
    6. Write markdown to output/ and append an AuditRecord.
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.audit import log_run
from src.config import MODEL_NAME, OUTPUT_DIR
from src.downloader import download_report
from src.models import AuditRecord
from src.parser import (
    compute_hash,
    extract_text,
    get_page_count,
    split_into_sections,
)
from src.summarizer import (
    format_summary,
    summarize_section,
    synthesize_summary,
)

console = Console(force_terminal=True, force_jupyter=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(url: str) -> Path:
    run_id = uuid.uuid4().hex[:12]
    started = _now_iso()
    console.rule(f"[bold cyan]BriefForge run {run_id}")
    console.print(f"[dim]URL:[/dim] {url}")

    audit_kwargs = {
        "run_id": run_id,
        "source_url": url,
        "pdf_hash": "",
        "timestamp": started,
        "model": MODEL_NAME,
        "page_count": 0,
        "output_path": "",
        "status": "started",
    }

    pdf_path = ""
    output_path: Path | None = None

    try:
        # 1. Download
        with console.status("[bold green]Downloading report PDF..."):
            pdf_path = download_report(url)
        console.print(f"[green][OK][/green] PDF saved: {pdf_path}")

        # 2. Hash + pages + text
        with console.status("[bold green]Hashing & extracting text..."):
            pdf_hash = compute_hash(pdf_path)
            pages = get_page_count(pdf_path)
            text, offsets = extract_text(pdf_path)
        audit_kwargs["pdf_hash"] = pdf_hash
        audit_kwargs["page_count"] = pages
        console.print(
            f"[green][OK][/green] {pages} pages, "
            f"{len(text):,} chars, sha256 {pdf_hash[:12]}..."
        )

        # 3. Split
        sections = split_into_sections(text, offsets)
        if not sections:
            raise RuntimeError("No sections extracted from PDF.")
        console.print(f"[green][OK][/green] {len(sections)} sections")

        # 4. MAP
        section_summaries = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Summarizing sections", total=len(sections)
            )
            for i, sec in enumerate(sections, 1):
                progress.update(
                    task,
                    description=(
                        f"Summarizing {i}/{len(sections)}: "
                        f"{sec['title'][:50]}"
                    ),
                )
                section_summaries.append(summarize_section(sec))
                progress.advance(task)

        # 5. REDUCE
        metadata = {
            "report_title": Path(pdf_path).stem.replace("-", " ").title(),
            "source": "J.P. Morgan Wealth Management",
            "report_date": "",
            "page_count": pages,
            "source_url": url,
        }
        with console.status("[bold green]Synthesizing executive summary..."):
            exec_summary = synthesize_summary(section_summaries, metadata)
        console.print("[green][OK][/green] Executive summary ready")

        # 6. Save
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"summary_{ts}_{run_id}.md"
        md = format_summary(exec_summary)
        output_path.write_text(md, encoding="utf-8")
        audit_kwargs["output_path"] = str(output_path.resolve())
        audit_kwargs["status"] = "success"

        console.rule("[bold cyan]Executive Summary")
        console.print(Panel(Markdown(md), border_style="cyan"))
        console.print(f"[bold green]Saved:[/bold green] {output_path}")
        return output_path

    except Exception as exc:  # noqa: BLE001 - top-level pipeline guard
        audit_kwargs["status"] = f"failed: {exc.__class__.__name__}: {exc}"
        console.print(
            Panel.fit(
                f"[red]Pipeline failed:[/red] {exc}",
                border_style="red",
                title="ERROR",
            )
        )
        raise
    finally:
        try:
            log_run(AuditRecord(**audit_kwargs))
        except Exception as log_exc:  # noqa: BLE001
            console.print(f"[yellow]audit log write failed:[/yellow] {log_exc}")


def main() -> int:
    if len(sys.argv) < 2:
        console.print("Usage: python pipeline.py <url>")
        return 2
    try:
        run(sys.argv[1])
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
