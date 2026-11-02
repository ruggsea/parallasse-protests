#!/usr/bin/env python3
"""Custom scraper for mongolianminingjournal.com.
Collects article URLs published between 2026-09-25 and 2026-10-25.
Writes tab‑separated lines ``URL<TAB>YYYY-MM-DD`` to
``data/urls_custom/mongolianminingjournal-com.tsv`` and updates a JSON
note file.
All HTTP requests use ``polite_fetch.fetch`` which respects robots.txt
and rate limits.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Import the project's polite fetch helper.
try:
    from polite_fetch import fetch
except ImportError:
    # Fallback for local debugging – very simple urllib fetch.
    import urllib.request
    def fetch(url, method="GET", timeout=30):
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": resp.getcode(), "text": resp.read().decode("utf-8", errors="ignore")}

BASE_DOMAIN = "www.mongolianminingjournal.com"
CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
START_STR = "2026-09-25"
END_STR = "2026-10-25"
START_DATE = datetime.strptime(START_STR, "%Y-%m-%d")
END_DATE = datetime.strptime(END_STR, "%Y-%m-%d")

OUTPUT_TSV = Path("data/urls_custom/mongolianminingjournal-com.tsv")
NOTE_JSON = Path("grids/custom/out/mongolianminingjournal-com.json.part")

def fetch_cdx():
    """Query Wayback CDX API for URLs in the date range using a direct request.
    Returns a list of original URLs (strings)."""
    import urllib.request, urllib.parse
    params = {
        "url": f"{BASE_DOMAIN}/*",
        "from": START_DATE.strftime("%Y%m%d"),
        "to": END_DATE.strftime("%Y%m%d"),
        "output": "json",
        "collapse": "urlkey",
    }
    query = "?" + urllib.parse.urlencode(params)
    url = CDX_ENDPOINT + query
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = resp.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"CDX request failed: {e}")
    data = json.loads(raw)
    urls = []
    for row in data[1:]:
        urls.append(row[2])
    return urls

def extract_pub_date(html: str) -> str:
    """Extract ISO date from og:article:published_time meta tag.
    Returns ``YYYY-MM-DD`` or ``None`` if not found.
    """
    m = re.search(r'og:article:published_time"\s+content="([0-9T:+-]+)"', html)
    if not m:
        return None
    iso = m.group(1)
    # Parse to datetime, ignore timezone offset.
    try:
        dt = datetime.fromisoformat(iso.rstrip('Z'))
    except Exception:
        return None
    return dt.strftime("%Y-%m-%d")

def main():
    # Step 1: get candidate URLs from CDX.
    try:
        candidates = fetch_cdx()
    except Exception as e:
        print(f"Failed to fetch CDX data: {e}", file=sys.stderr)
        sys.exit(1)

    # Deduplicate.
    unique_urls = list(dict.fromkeys(candidates))
    results = []  # list of (url, date)
    per_day_counts = {}

    for url in unique_urls:
        # Fetch article page.
        try:
            resp = fetch(url)
            if resp.get("status") != 200:
                continue
            html = resp.get("text") if isinstance(resp, dict) else str(resp)
        except Exception:
            continue
        pub_date = extract_pub_date(html)
        if not pub_date:
            continue
        # Filter by range.
        if START_STR <= pub_date <= END_STR:
            results.append((url, pub_date))
            per_day_counts[pub_date] = per_day_counts.get(pub_date, 0) + 1

    # Write TSV.
    OUTPUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with OUTPUT_TSV.open("w", encoding="utf-8") as f:
        for url, date in results:
            if url in seen:
                continue
            seen.add(url)
            f.write(f"{url}\t{date}\n")

    # Print per‑day summary.
    for day in sorted(per_day_counts):
        print(f"{day}: {per_day_counts[day]} URLs")
    print(f"Wrote {len(seen)} unique URLs to {OUTPUT_TSV}")

    # Update note JSON.
    notes = {
        "script": "scrapers/custom/mongolianminingjournal-com.py",
        "notes": f"Fetched {len(seen)} URLs via Wayback CDX and extracted dates from og:article:published_time meta tags.",
        "status": "completed",
    }
    NOTE_JSON.parent.mkdir(parents=True, exist_ok=True)
    NOTE_JSON.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
