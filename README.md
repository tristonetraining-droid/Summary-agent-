# CIMSummarizer — Tristone Strategic Partners

AI-assisted pipeline: CIM PDF → 4-page editable Deal Summary → DOCX / PDF export.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) (for PDF export — install and ensure `soffice` is on PATH)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) on PATH (for `pdf2image` page rasterization — Windows: unzip and add `bin/` to PATH)

---

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Set your Anthropic API key in `backend/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Place Tristone's `CIM_Template.docx` in `backend/templates/` (optional — if absent, a generated layout is used).

Start the API:
```bash
cd backend
python service.py
# → http://localhost:8000
```

---

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

### 3. Use

1. Open **http://localhost:3000**
2. Drop a CIM PDF, enter deal name + sponsor, click **Start summarization**
3. Watch the live 5-stage progress timeline (~2–5 min)
4. Edit page opens automatically — live WYSIWYG preview on the left, collapsible section editors on the right
5. Click **Export PDF** (server-side LibreOffice) or **DOCX** to download

---

## CLI (no frontend needed)

```bash
cd backend
.venv\Scripts\activate
python pipeline.py "path/to/CIM.pdf" --deal "Tailwind" --sponsor "ABC Capital" --out ./out
```

Outputs: `out/CIM_Summary_Tailwind.docx` + `out/summary.json`

---

## Architecture

```
Stage 1 INGEST     pdfplumber extracts text + tables per page; pdf2image rasterizes
Stage 2 CLASSIFY   Claude Sonnet maps CIM pages → 11 output sections
Stage 3 EXTRACT    Claude Haiku (parallel) extracts each section → Pydantic model
Stage 4 SYNTHESIZE Claude Sonnet: tone correction, consistency, S&U validation
Stage 5 ASSEMBLE   python-docx populates template → .docx
Stage 6 EXPORT     LibreOffice headless converts .docx → .pdf
```

## File Structure

```
backend/
  pipeline.py          CLI entry point
  service.py           FastAPI + SSE
  src/
    config.py          env + constants
    models.py          Pydantic CIMSummary + JobState
    ingest.py          PDF extraction
    classifier.py      Section mapping
    extractors.py      11 parallel Claude Haiku extractors
    synthesizer.py     Tone + consistency pass
    assembler.py       python-docx DOCX builder
    pdf_export.py      LibreOffice PDF conversion
    pipeline_core.py   Orchestrator
    jobs.py            Job registry (in-memory + on-disk)
    llm.py             Anthropic client wrapper (tool_use → Pydantic)
    prompts/
      classifier.txt   Section classifier prompt
      tone_rules.txt   PE language rules (applied to all extractors)
      sections.py      Per-section extractor prompts + synthesizer
  templates/
    CIM_Template.docx  Tristone template (add manually)

frontend/
  app/
    page.tsx                   Upload + deal form
    jobs/[id]/page.tsx         Live progress (SSE)
    jobs/[id]/edit/page.tsx    Editable preview + export
  components/
    DealSummaryPreview.tsx     4-page WYSIWYG (template-matching CSS)
    SectionEditors.tsx         Collapsible per-section editors
  lib/
    types.ts                   TypeScript mirrors of Pydantic models
    api.ts                     Fetch wrappers
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Anthropic API key |
| `CLAUDE_MODEL_SONNET` | `claude-sonnet-4-5` | Classifier + synthesizer model |
| `CLAUDE_MODEL_HAIKU` | `claude-haiku-4-5` | Per-section extractor model |
| `JOBS_DIR` | `./.jobs` | Job state + uploads storage |
| `TEMPLATE_PATH` | `./templates/CIM_Template.docx` | Tristone DOCX template |
| `LIBREOFFICE_BIN` | `soffice` | LibreOffice binary name |
| `ALLOW_ORIGINS` | `http://localhost:3000` | CORS origins (comma-separated) |

## Phase 2 (next)
- n8n email trigger → POST /api/jobs
- PostgreSQL audit log
- FastAPI deployment on Railway / Tristone VPS
- OCR fallback for scanned CIMs (pytesseract)
