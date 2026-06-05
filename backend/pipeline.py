"""CLI: python pipeline.py <cim.pdf> --deal "Tailwind" --sponsor "ABC Capital" --out ./out"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from src.models import JobStage
from src.pipeline_core import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--deal", required=True)
    parser.add_argument("--sponsor", default="")
    parser.add_argument("--out", type=Path, default=Path("./out"))
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    console = Console()
    args.out.mkdir(parents=True, exist_ok=True)

    with Progress() as prog:
        task = prog.add_task("Processing", total=1.0)

        def cb(stage: JobStage, msg: str, p: float) -> None:
            prog.update(task, completed=p, description=f"[{stage.value}] {msg}")

        summary, docx, pages = run_pipeline(
            pdf_path=args.pdf,
            job_dir=args.out,
            deal_name=args.deal,
            sponsor_name=args.sponsor,
            on_progress=cb,
        )

    console.print(f"\n[green]Done.[/] DOCX: {docx}")
    console.print(f"Rasterized pages: {pages}")
    (args.out / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"Summary JSON: {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
