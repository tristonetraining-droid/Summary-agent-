"""Quick test script for the /summarize endpoint."""
import httpx
import json
import sys

import os
BASE = os.getenv("BRIEFFORGE_URL", "http://127.0.0.1:8000").rstrip("/")

def test_summarize():
    print("=== Testing POST /summarize ===")
    r = httpx.post(
        f"{BASE}/summarize",
        json={
            "source_url": "https://www.chase.com/personal/investments/mid-year-outlook",
            "message_id": "test-001",
        },
        timeout=httpx.Timeout(600.0),
    )
    data = r.json()
    print(f"HTTP {r.status_code}")
    print(f"status: {data['status']}")
    print(f"audit_id: {data['audit_id']}")
    print(f"page_count: {data['page_count']}")
    hash_val = data.get("source_pdf_hash") or ""
    print(f"pdf_hash: {hash_val[:16]}..." if hash_val else "pdf_hash: none")
    print(f"response_time_ms: {data['response_time_ms']}")
    print(f"error: {data['error']}")
    print(f"summary_md length: {len(data['summary_markdown'] or '')} chars")
    print(f"summary_html length: {len(data['summary_html'] or '')} chars")
    print("--- FIRST 300 chars of markdown ---")
    print((data["summary_markdown"] or "")[:300])
    return data


def test_idempotency():
    print("\n=== Testing idempotency (same message_id) ===")
    r = httpx.post(
        f"{BASE}/summarize",
        json={
            "source_url": "https://www.chase.com/personal/investments/mid-year-outlook",
            "message_id": "test-001",
        },
        timeout=30,
    )
    data = r.json()
    print(f"HTTP {r.status_code}")
    print(f"status: {data['status']}  (should be 'duplicate')")
    print(f"response_time_ms: {data['response_time_ms']}  (should be ~0)")


if __name__ == "__main__":
    data = test_summarize()
    if data["status"] == "success":
        test_idempotency()
    else:
        print(f"\nFirst call failed, skipping idempotency test: {data['error']}")
        sys.exit(1)
