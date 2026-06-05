"""Playwright-based downloader: landing-page URL -> local PDF path.

Strategy (in order, fail open to next):
  0. If URL already ends in .pdf, fetch it directly.
  1. Open landing page, click a "Read the report" / PDF button and capture
     the resulting `download` event (Case A).
  2. If no download fires, look for the PDF URL in: new-tab navigation,
     anchor hrefs, or network responses with application/pdf, then fetch
     it via the browser's request context (Case B).

Every external call is wrapped in try/except so failures surface with a
clear message rather than producing garbage downstream.
"""
from __future__ import annotations

import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import (
    Download,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .config import (
    DOWNLOAD_TIMEOUT_MS,
    PAGE_LOAD_TIMEOUT_MS,
    SAMPLES_DIR,
    USER_AGENT,
    VIEWPORT,
)

# Selectors tried in order on the landing page.
BUTTON_SELECTORS: list[str] = [
    "a:has-text('Read the report (PDF)')",
    "a:has-text('Read the report')",
    "button:has-text('Read the report')",
    "a:has-text('Read the full report')",
    "a:has-text('Download the report')",
    "a:has-text('View the report')",
    "a:has-text('PDF')",
    "a[href$='.pdf']",
    "a[href*='.pdf']",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _slug_from_url(url: str) -> str:
    path = urlparse(url).path or "report"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path).strip("-/") or "report"
    return slug[:60]


def _dest_path(url: str, content: bytes | None = None) -> Path:
    """Build a deterministic destination path under samples/."""
    if content is not None:
        digest = hashlib.sha256(content).hexdigest()[:12]
    else:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    slug = _slug_from_url(url)
    name = f"{slug}-{digest}.pdf"
    return SAMPLES_DIR / name


def _is_pdf_bytes(blob: bytes) -> bool:
    return blob[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Core download paths
# ---------------------------------------------------------------------------
def _direct_pdf_download(url: str, page: Page) -> Path | None:
    """If URL is itself a PDF, fetch it through the browser context."""
    if not url.lower().split("?")[0].endswith(".pdf"):
        return None
    try:
        resp = page.context.request.get(url, timeout=DOWNLOAD_TIMEOUT_MS)
    except PlaywrightError as exc:
        raise RuntimeError(f"Direct PDF fetch failed for {url}: {exc}") from exc
    if not resp.ok:
        raise RuntimeError(
            f"Direct PDF fetch returned HTTP {resp.status} for {url}"
        )
    blob = resp.body()
    if not _is_pdf_bytes(blob):
        raise RuntimeError(
            f"URL ended in .pdf but server returned non-PDF content ({len(blob)} bytes)."
        )
    dest = _dest_path(url, blob)
    dest.write_bytes(blob)
    return dest


def _try_click_and_download(page: Page, url: str) -> Path | None:
    """Case A: click triggers a download event."""
    for sel in BUTTON_SELECTORS:
        locator = page.locator(sel).first
        try:
            if locator.count() == 0:
                continue
        except PlaywrightError:
            continue
        try:
            with page.expect_download(timeout=15_000) as dl_info:
                locator.click(timeout=10_000)
            download: Download = dl_info.value
            suggested = download.suggested_filename or "report.pdf"
            tmp = SAMPLES_DIR / f"_tmp_{int(time.time())}_{suggested}"
            download.save_as(tmp)
            blob = tmp.read_bytes()
            if not _is_pdf_bytes(blob):
                tmp.unlink(missing_ok=True)
                continue
            dest = _dest_path(url, blob)
            tmp.replace(dest)
            return dest
        except PlaywrightTimeoutError:
            # Click happened but no download event — likely a navigation case.
            return None
        except PlaywrightError:
            continue
    return None


def _try_capture_pdf_url(page: Page, url: str) -> Path | None:
    """Case B: find a PDF URL on the page (anchors, new tab) and fetch it."""
    candidate_urls: list[str] = []

    # 1. Any anchor pointing at a PDF.
    try:
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href)",
        )
        candidate_urls.extend(
            h for h in hrefs if isinstance(h, str) and ".pdf" in h.lower()
        )
    except PlaywrightError:
        pass

    # 2. Click each button selector and see if it pops a new page or navigates.
    if not candidate_urls:
        for sel in BUTTON_SELECTORS:
            locator = page.locator(sel).first
            try:
                if locator.count() == 0:
                    continue
            except PlaywrightError:
                continue
            try:
                with page.context.expect_page(timeout=8_000) as new_page_info:
                    locator.click(timeout=8_000)
                new_page = new_page_info.value
                new_page.wait_for_load_state(
                    "domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS
                )
                if ".pdf" in new_page.url.lower():
                    candidate_urls.append(new_page.url)
                    break
            except (PlaywrightTimeoutError, PlaywrightError):
                # Fallback: maybe it navigated the same tab.
                if ".pdf" in page.url.lower():
                    candidate_urls.append(page.url)
                    break
                continue

    # Deduplicate, keep order.
    seen: set[str] = set()
    unique = [u for u in candidate_urls if not (u in seen or seen.add(u))]

    for pdf_url in unique:
        try:
            resp = page.context.request.get(
                pdf_url, timeout=DOWNLOAD_TIMEOUT_MS
            )
        except PlaywrightError:
            continue
        if not resp.ok:
            continue
        blob = resp.body()
        if not _is_pdf_bytes(blob):
            continue
        dest = _dest_path(pdf_url, blob)
        dest.write_bytes(blob)
        return dest

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def download_report(url: str, headless: bool = True) -> str:
    """Download the report PDF for the given landing-page URL.

    Returns the absolute local path to the saved PDF.
    Raises RuntimeError with a clear message on any failure.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL: {url!r}")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except PlaywrightError as exc:
            raise RuntimeError(
                "Failed to launch Chromium. Did you run `playwright install chromium`?"
            ) from exc

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            accept_downloads=True,
        )
        page = context.new_page()
        page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)

        try:
            # Case 0: URL is already a direct PDF link.
            direct = _direct_pdf_download(url, page)
            if direct is not None:
                return str(direct.resolve())

            # Navigate to the landing page.
            try:
                page.goto(url, wait_until="domcontentloaded",
                          timeout=PAGE_LOAD_TIMEOUT_MS)
                try:
                    page.wait_for_load_state(
                        "networkidle", timeout=15_000
                    )
                except PlaywrightTimeoutError:
                    pass  # JS-heavy pages may never go fully idle.
            except PlaywrightError as exc:
                raise RuntimeError(
                    f"Failed to load landing page {url}: {exc}"
                ) from exc

            # Small human-like pause.
            time.sleep(1.0)

            # Case A: click triggers download.
            dl = _try_click_and_download(page, url)
            if dl is not None:
                return str(dl.resolve())

            # Case B: capture PDF URL from page/new tab and fetch.
            dl = _try_capture_pdf_url(page, url)
            if dl is not None:
                return str(dl.resolve())

            raise RuntimeError(
                "Could not locate a PDF on the landing page. Tried button "
                "selectors, anchor scan, and new-tab capture. Page URL: "
                f"{page.url}"
            )
        finally:
            try:
                context.close()
                browser.close()
            except PlaywrightError:
                pass


# ---------------------------------------------------------------------------
# CLI: `python -m src.downloader <url>`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.downloader <url>", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]
    try:
        path = download_report(target)
    except Exception as exc:  # noqa: BLE001 - top-level CLI guard
        print(f"[downloader] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(path)
