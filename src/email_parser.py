"""Extract report URLs from forwarded email content.

Scans both plain-text and HTML email bodies for links matching known
financial report domains. Priority order:
  1. Explicit "read the report" anchor links
  2. Any URL on the allowlisted domains

Domain allowlist covers the major institutional research sources that
Tristone processes.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ALLOWED_DOMAINS: list[str] = [
    "chase.com",
    "jpmorgan.com",
    "jpmorganchase.com",
    "jpmorganmarkets.com",
    "gs.com",
    "morganstanley.com",
    "goldmansachs.com",
    "blackrock.com",
    "fidelity.com",
]

# Patterns that suggest a "read the report" CTA (case-insensitive)
CTA_PATTERNS: list[re.Pattern] = [
    re.compile(r"read\s+the\s+(full\s+)?report", re.IGNORECASE),
    re.compile(r"view\s+the\s+(full\s+)?report", re.IGNORECASE),
    re.compile(r"download\s+(the\s+)?(full\s+)?report", re.IGNORECASE),
    re.compile(r"access\s+the\s+report", re.IGNORECASE),
    re.compile(r"read\s+(the\s+)?outlook", re.IGNORECASE),
    re.compile(r"mid[- ]year\s+outlook", re.IGNORECASE),
]

# Regex to pull href from anchor tags
_HREF_RE = re.compile(
    r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

# Regex to find bare URLs in plain text
_URL_RE = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _domain_matches(url: str) -> bool:
    """Check if URL's domain is in our allowlist."""
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        return any(host == d or host.endswith(f".{d}") for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def _clean_url(url: str) -> str:
    """Unescape HTML entities and strip trailing punctuation."""
    url = unescape(url)
    # Strip common trailing chars that get accidentally included
    url = url.rstrip(".,;:!?")
    return url


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_report_url(
    email_body: str,
    email_html: str | None = None,
) -> str | None:
    """Extract the highest-priority report URL from email content.

    Args:
        email_body: Plain-text email body (or full HTML if html not separate).
        email_html: Optional HTML body (preferred source for anchor links).

    Returns:
        The best matching URL, or None if no match found.
    """
    html_source = email_html or email_body

    # --- Strategy 1: Find CTA anchor links in HTML ---
    cta_urls: list[str] = []
    for match in _HREF_RE.finditer(html_source):
        href = _clean_url(match.group(1))
        anchor_text = match.group(2)
        # Check if anchor text matches a CTA pattern
        for pattern in CTA_PATTERNS:
            if pattern.search(anchor_text):
                if _domain_matches(href):
                    cta_urls.append(href)
                break

    if cta_urls:
        return cta_urls[0]

    # --- Strategy 2: Find any allowlisted domain URL in HTML anchors ---
    anchor_urls: list[str] = []
    for match in _HREF_RE.finditer(html_source):
        href = _clean_url(match.group(1))
        if _domain_matches(href):
            anchor_urls.append(href)

    if anchor_urls:
        return anchor_urls[0]

    # --- Strategy 3: Bare URLs in plain text ---
    for url_match in _URL_RE.finditer(email_body):
        url = _clean_url(url_match.group(0))
        if _domain_matches(url):
            return url

    return None


def extract_all_report_urls(
    email_body: str,
    email_html: str | None = None,
) -> list[str]:
    """Extract ALL matching report URLs (for multi-report emails)."""
    html_source = email_html or email_body
    seen: set[str] = set()
    results: list[str] = []

    # From HTML anchors
    for match in _HREF_RE.finditer(html_source):
        href = _clean_url(match.group(1))
        if _domain_matches(href) and href not in seen:
            seen.add(href)
            results.append(href)

    # From plain text
    for url_match in _URL_RE.finditer(email_body):
        url = _clean_url(url_match.group(0))
        if _domain_matches(url) and url not in seen:
            seen.add(url)
            results.append(url)

    return results


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.email_parser <email_file.html>")
        sys.exit(1)

    from pathlib import Path

    content = Path(sys.argv[1]).read_text(encoding="utf-8")
    url = extract_report_url(content, content)
    print(f"Extracted URL: {url}")
    all_urls = extract_all_report_urls(content, content)
    print(f"All URLs: {all_urls}")
