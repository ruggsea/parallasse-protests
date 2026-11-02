#!/usr/bin/env python3

"""Scrape article URLs from La Voix du Nord (lavoixdunord.fr) for the date range
2026-09-25 to 2026-10-25.

Uses the Wayback Machine CDX API as a fallback because the site blocks direct
fetches. The CDX API returns captured URLs with timestamps. We filter to the
desired window, deduplicate, and write a TSV of ``URL<TAB>YYYY-MM-DD``.
"""

import json
import sys
import os
from datetime import datetime, timedelta

# Ensure the repository root is on sys.path for polite_fetch
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# Add the project root and the scrapers directory so that polite_fetch can be imported
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, "scrapers"))

try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch not found; ensure script runs from project root\n")
    sys.exit(1)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?url=lavoixdunord.fr/*"
    f"&from={START.strftime('%Y%m%d')}&to={END.strftime('%Y%m%d')}"
    "&output=json&collapse=urlkey"
)

# Fetch with simple retries (max 3 attempts)
max_tries = 3
for attempt in range(1, max_tries + 1):
    status, text, _ = fetch(CDX_URL)
    if status == 200:
        break
    sys.stderr.write(f"Attempt {attempt} failed: HTTP {status}\n")
    if attempt < max_tries:
        import time
        time.sleep(attempt * 2)  # exponential back‑off
else:
    sys.stderr.write(f"Failed to fetch CDX data after {max_tries} attempts\n")
    sys.exit(1)

try:
    data = json.loads(text)
except json.JSONDecodeError as e:
    sys.stderr.write(f"JSON decode error: {e}\n")
    sys.exit(1)

# First line is header
header = data[0]
idx_url = header.index('url') if 'url' in header else 1  # fallback
idx_timestamp = header.index('timestamp') if 'timestamp' in header else 2

url_to_date = {}
for row in data[1:]:
    url = row[idx_url]
    ts = row[idx_timestamp]
    # Timestamp format: YYYYMMDDhhmmss
    try:
        dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
    except ValueError:
        continue
    if not (START <= dt <= END):
        continue
    date_str = dt.strftime("%Y-%m-%d")
    # Keep first occurrence (earliest capture) – CDX with collapse=urlkey returns earliest
    if url not in url_to_date:
        url_to_date[url] = date_str

# Prepare output directory
out_path = os.path.abspath(os.path.join(repo_root, "data/urls_custom/lavoixdunord-fr.tsv"))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Write TSV sorted by date then URL
with open(out_path, "w", encoding="utf-8") as f:
    for url, date in sorted(url_to_date.items(), key=lambda x: (x[1], x[0])):
        f.write(f"{url}\t{date}\n")

# Print per‑day counts
counts = {}
for d in url_to_date.values():
    counts[d] = counts.get(d, 0) + 1
for day in sorted(counts):
    print(f"{day}\t{counts[day]}")

print(f"Wrote {len(url_to_date)} URLs to {out_path}")
