"""PDF parsing: hash, page count, text extraction, and section splitting.

Designed to handle 70-page reports without blowing up:
  - pages are read one at a time and joined incrementally
  - section detection is heuristic (heading-like lines) with a clean
    fallback to even-sized chunks so we never silently truncate.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import TypedDict

import pdfplumber

from .config import CHUNK_SIZE, TARGET_CHUNKS


class Section(TypedDict):
    title: str
    text: str
    approx_pages: str  # e.g. "12-18"


# ---------------------------------------------------------------------------
# Basic file-level operations
# ---------------------------------------------------------------------------
def compute_hash(pdf_path: str | Path) -> str:
    """SHA-256 of the raw PDF bytes (for audit trail)."""
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"Failed to read PDF for hashing: {exc}") from exc
    return h.hexdigest()


def get_page_count(pdf_path: str | Path) -> int:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            return len(pdf.pages)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to read PDF page count: {exc}") from exc


def extract_text(pdf_path: str | Path) -> tuple[str, list[tuple[int, int]]]:
    """Extract all text from the PDF.

    Returns (full_text, page_offsets) where page_offsets[i] = (start, end)
    character offsets of page i+1 inside full_text. We keep the offsets so
    that section splitting can attach an approximate page range to each
    section.
    """
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                try:
                    txt = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    # A single broken page must not kill the whole extraction.
                    txt = ""
                # Normalize whitespace per page; keep page breaks explicit.
                txt = re.sub(r"[ \t]+", " ", txt)
                txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
                start = cursor
                parts.append(txt)
                cursor += len(txt) + 2  # for the joining "\n\n"
                end = cursor
                offsets.append((start, end))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to extract PDF text: {exc}") from exc

    return "\n\n".join(parts), offsets


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------
# A "heading" line is short, mostly title-cased / uppercase, has no
# terminal punctuation, and isn't a page number.
_HEADING_RE = re.compile(
    r"^(?P<line>(?:[A-Z][A-Za-z0-9&\-/,.()' ]{2,80}))$"
)


def _looks_like_heading(line: str) -> bool:
    line = line.strip()
    if not (3 <= len(line) <= 90):
        return False
    if line.endswith((".", "?", "!", ",", ";", ":")):
        return False
    if re.fullmatch(r"[\d\s\-\.]+", line):
        return False
    # Require either ALL CAPS, or Title Case with >=2 words and mostly cap-initial.
    if line.isupper() and any(c.isalpha() for c in line):
        return True
    words = line.split()
    if len(words) >= 2:
        cap = sum(1 for w in words if w[:1].isupper())
        if cap / len(words) >= 0.6 and not _HEADING_RE.match(line) is None:
            return True
    return False


def _page_range_for_offsets(
    start: int, end: int, page_offsets: list[tuple[int, int]]
) -> str:
    if not page_offsets:
        return ""
    first = last = None
    for i, (ps, pe) in enumerate(page_offsets, start=1):
        if pe <= start:
            continue
        if ps >= end:
            break
        if first is None:
            first = i
        last = i
    if first is None or last is None:
        return ""
    return f"{first}" if first == last else f"{first}-{last}"


def _heading_split(
    text: str, page_offsets: list[tuple[int, int]]
) -> list[Section]:
    """Split on heading-like lines. Returns [] if too few headings found."""
    lines = text.split("\n")
    # Reconstruct char offsets per line so we can attribute pages.
    line_offsets: list[int] = []
    pos = 0
    for ln in lines:
        line_offsets.append(pos)
        pos += len(ln) + 1  # +1 for the "\n"

    boundaries: list[tuple[int, int, str]] = []  # (line_idx, char_offset, title)
    for i, ln in enumerate(lines):
        if _looks_like_heading(ln):
            boundaries.append((i, line_offsets[i], ln.strip()))

    # Need enough headings to be a meaningful split.
    if len(boundaries) < 4:
        return []

    sections: list[Section] = []
    for idx, (line_idx, char_off, title) in enumerate(boundaries):
        next_off = (
            boundaries[idx + 1][1] if idx + 1 < len(boundaries) else len(text)
        )
        body = text[char_off + len(title): next_off].strip()
        if len(body) < 200:
            # Skip pseudo-headings that have no real body.
            continue
        sections.append(
            {
                "title": title,
                "text": body,
                "approx_pages": _page_range_for_offsets(
                    char_off, next_off, page_offsets
                ),
            }
        )

    return sections


def _even_split(
    text: str,
    page_offsets: list[tuple[int, int]],
    target_chunks: int,
) -> list[Section]:
    """Fallback: even-sized chunks, broken at paragraph boundaries when possible."""
    if not text:
        return []
    target = max(1, target_chunks)
    approx_size = max(CHUNK_SIZE, len(text) // target + 1)

    sections: list[Section] = []
    start = 0
    idx = 1
    while start < len(text):
        end = min(start + approx_size, len(text))
        # Try to break on a paragraph boundary nearby.
        if end < len(text):
            window = text.rfind("\n\n", start + approx_size // 2, end)
            if window != -1:
                end = window
        body = text[start:end].strip()
        if body:
            sections.append(
                {
                    "title": f"Section {idx}",
                    "text": body,
                    "approx_pages": _page_range_for_offsets(
                        start, end, page_offsets
                    ),
                }
            )
            idx += 1
        start = end
    return sections


def split_into_sections(
    text: str,
    page_offsets: list[tuple[int, int]] | None = None,
    target_chunks: int = TARGET_CHUNKS,
) -> list[Section]:
    """Split the report text into sections.

    Heading-based split is tried first; if it yields too few or too many
    sections, fall back to even-sized chunks. Either way, every chunk
    carries an approximate page range.
    """
    page_offsets = page_offsets or []

    headings = _heading_split(text, page_offsets)
    # Accept heading split only if it's in a reasonable range.
    if 4 <= len(headings) <= target_chunks * 3:
        # If there are too many tiny headings, merge until we approach target_chunks.
        while len(headings) > target_chunks:
            # Merge the smallest section with its neighbour.
            i_min = min(
                range(len(headings)), key=lambda i: len(headings[i]["text"])
            )
            j = i_min - 1 if i_min > 0 else 1
            merged_title = headings[min(i_min, j)]["title"]
            merged_text = (
                headings[min(i_min, j)]["text"]
                + "\n\n"
                + headings[max(i_min, j)]["text"]
            )
            merged_pages = "-".join(
                p for p in (
                    headings[min(i_min, j)]["approx_pages"],
                    headings[max(i_min, j)]["approx_pages"],
                ) if p
            )
            new_section: Section = {
                "title": merged_title,
                "text": merged_text,
                "approx_pages": merged_pages,
            }
            headings = (
                headings[: min(i_min, j)]
                + [new_section]
                + headings[max(i_min, j) + 1:]
            )
        return headings

    return _even_split(text, page_offsets, target_chunks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.parser <pdf_path>", file=sys.stderr)
        sys.exit(2)
    pdf = sys.argv[1]
    try:
        pages = get_page_count(pdf)
        h = compute_hash(pdf)
        text, offsets = extract_text(pdf)
        sections = split_into_sections(text, offsets)
    except Exception as exc:  # noqa: BLE001
        print(f"[parser] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"path:     {pdf}")
    print(f"pages:    {pages}")
    print(f"sha256:   {h}")
    print(f"chars:    {len(text):,}")
    print(f"sections: {len(sections)}")
    for i, s in enumerate(sections, 1):
        print(
            f"  {i:>2}. [{s['approx_pages'] or '?':>6}] "
            f"{s['title'][:70]}  ({len(s['text']):,} chars)"
        )
