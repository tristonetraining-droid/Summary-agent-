# BriefForge

Autonomous agent for **Tristone Strategic Partners** that turns institutional
research reports (primarily J.P. Morgan / Chase Wealth Management) into
one-page executive summaries for the CEO.

**Day 1 scope:** local pipeline only — URL in, polished markdown summary out.
No email integration, no orchestrator, no deployment yet.

```
landing-page URL
      |
      v
[Playwright] -- click "Read the report (PDF)" --> PDF file
      |
      v
[pdfplumber] -- hash + page count + text + section split
      |
      v
[Claude MAP]  -- per-section grounded summaries  (structured tool use)
      |
      v
[Claude REDUCE] -- one-page ExecutiveSummary    (structured tool use)
      |
      v
output/summary_<ts>_<run_id>.md + audit_log.json
```

## Guardrails

- **Grounding** — every figure must trace to the source report. Claude is
  pinned to structured tool output that mirrors our Pydantic models, so it
  cannot invent fields. The MAP step explicitly tells the model to use
  only facts present in the section text.
- **Audit** — every run appends an `AuditRecord` to `output/audit_log.json`
  (run id, source URL, PDF SHA-256, timestamp, model, page count, output
  path, status).
- **Secrets** — `ANTHROPIC_API_KEY` is loaded from `.env` only.
- **No silent truncation** — long reports go through map-reduce; we never
  cut content to fit a context window.
- **Error handling** — every external call (Playwright nav, PDF parse,
  Claude call) is wrapped with a clear, actionable message on failure.

## Setup (Windows / PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
# then edit .env and paste your ANTHROPIC_API_KEY
```

## Run

```powershell
python pipeline.py "https://www.chase.com/personal/investments/mid-year-outlook"
```

You will see download progress, per-section MAP progress, a synthesis
step, and the final summary rendered in the terminal. The markdown file
lands in `output/`.

## Project layout

```
briefforge/
  pipeline.py            entry point: python pipeline.py <url>
  src/
    config.py            env loading, model constants, paths
    models.py            Pydantic schemas (SectionSummary, ExecutiveSummary, AuditRecord)
    downloader.py        Playwright: URL -> PDF (click / new-tab / direct)
    parser.py            PDF -> text + sections (heading-aware, even-split fallback)
    summarizer.py        Claude map-reduce with structured tool use
    audit.py             JSON audit log (Postgres in Day 2)
  samples/               downloaded PDFs
  output/                generated summaries + audit_log.json
```

## Roadmap

- **Day 2** — Postgres-backed audit, email ingest (IMAP / Gmail API),
  n8n orchestrator, deployment.

## Testing individual stages

```powershell
# models load
python -c "from src.models import ExecutiveSummary; print('ok')"

# downloader only
python -m src.downloader "<landing-page-url>"

# parser only
python -m src.parser samples\<your.pdf>
```
