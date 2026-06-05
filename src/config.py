"""Central configuration: environment loading, constants, and paths.

Secrets (API keys) are loaded from .env only and never hardcoded or logged.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Project root is the parent of the `src/` package directory.
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
SRC_DIR: Path = ROOT_DIR / "src"
SAMPLES_DIR: Path = ROOT_DIR / "samples"
OUTPUT_DIR: Path = ROOT_DIR / "output"

# Ensure working directories exist so downstream code can rely on them.
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_LOG_PATH: Path = OUTPUT_DIR / "audit_log.json"

# ---------------------------------------------------------------------------
# Environment / secrets
# ---------------------------------------------------------------------------
load_dotenv(ROOT_DIR / ".env")

ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")


def require_api_key() -> str:
    """Return the Anthropic API key or raise a clear error.

    We validate lazily (not at import time) so that phases which do not call
    Claude — e.g. the downloader or parser — can run without a key present.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key. The key must never be hardcoded or committed."
        )
    return ANTHROPIC_API_KEY


# ---------------------------------------------------------------------------
# Model / summarization constants
# ---------------------------------------------------------------------------
MODEL_NAME: str = "claude-sonnet-4-5"

# Soft cap on tokens we ask Claude to produce for a single section summary.
MAX_SECTION_TOKENS: int = 1024

# Token budget for the final reduce/synthesis call.
MAX_SUMMARY_TOKENS: int = 2048

# Approximate characters per section chunk during map-reduce splitting.
# ~4 chars/token, targeting comfortably below the model context per chunk.
CHUNK_SIZE: int = 12_000

# Default number of chunks we aim for when splitting a report.
TARGET_CHUNKS: int = 12

# Networking / browser behaviour
PAGE_LOAD_TIMEOUT_MS: int = 60_000
DOWNLOAD_TIMEOUT_MS: int = 60_000
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT: dict[str, int] = {"width": 1366, "height": 900}
