"""Central configuration for CIMSummarizer backend."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL_SONNET: str = os.getenv("CLAUDE_MODEL_SONNET", "claude-sonnet-4-5")
CLAUDE_MODEL_HAIKU: str = os.getenv("CLAUDE_MODEL_HAIKU", "claude-haiku-4-5")

JOBS_DIR: Path = Path(os.getenv("JOBS_DIR", ROOT_DIR / ".jobs")).resolve()
JOBS_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_PATH: Path = Path(
    os.getenv("TEMPLATE_PATH", ROOT_DIR / "templates" / "CIM_Template.docx")
).resolve()

PROMPTS_DIR: Path = ROOT_DIR / "src" / "prompts"

_WIN_SOFFICE = Path("C:/Program Files/LibreOffice/program/soffice.exe")
_libreoffice_default = str(_WIN_SOFFICE) if _WIN_SOFFICE.exists() else "soffice"
LIBREOFFICE_BIN: str = os.getenv("LIBREOFFICE_BIN", _libreoffice_default)

# Poppler binaries (pdf2image page rasterization)
# Default: bundled poppler-windows next to the project; override via env var
_default_poppler = (
    ROOT_DIR.parent / "poppler-windows" / "Release" / "poppler-24.08.0" / "Library" / "bin"
)
POPPLER_PATH: str = os.getenv("POPPLER_PATH", str(_default_poppler) if _default_poppler.exists() else "")

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

ALLOW_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOW_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# Pipeline tuning
CLASSIFIER_PAGE_TEXT_CHARS = 1500  # cap per-page text fed to classifier
MAX_PAGES_FOR_CLASSIFIER = 60
SECTION_TEXT_CHAR_BUDGET = 18000  # per-section extractor context window
DEFAULT_PAGE_DPI = 144

OUTPUT_SECTIONS = [
    "deal_header",
    "deal_overview",
    "deal_criteria",
    "company_overview",
    "sources_and_uses",
    "highlights_and_risks",
    "sponsor_value_creation",
    "product_offering",
    "industry_competitors",
    "customers_and_exit",
    "other_considerations",
    "sponsor_overview",
    "management_bios",
    "financials",
]
