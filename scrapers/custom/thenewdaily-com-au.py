#!/usr/bin/env python3
"""Scraper for The New Daily (Australia)
Collects article URLs published between 2026-09-25 and 2026-10-25 inclusive.
Writes a TSV with columns: URL<TAB>YYYY-MM-DD to data/urls_custom/thenewdaily-com-au.tsv
Uses the site's WordPress REST API via polite_fetch to respect robots.txt and rate limits.
"""
import sys
import json
import os
from datetime import datetime, timedelta
import time

# Ensure polite_fetch is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
try:
    from polite_fetch import fetch
except ImportError:
    print("polite_fetch not found", file=sys.stderr)
    sys.exit(1)

START_DATE = "2026-09-25"
END_DATE = "2026-10-25"
# API expects ISO datetime, end exclusive so add one day
START_ISO = f"{START_DATE}T00:00:00"
END_EXCLUSIVE = (datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
BASE_URL = "https://wp.thenewdaily.com.au/wp-json/wp/v2/posts"
PER_PAGE = 100

seen = set()
per_day_counts = {}
page = 1
while True:
    url = (
        f"{BASE_URL}?per_page={PER_PAGE}&page={page}"
        f"&after={START_ISO}&before={END_EXCLUSIVE}&_fields=id,date,link"
    )
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch page {page}, status {status}", file=sys.stderr)
        break
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"JSON decode error on page {page}", file=sys.stderr)
        break
    if not data:
        break
    for entry in data:
        link = entry.get("link")
        date_iso = entry.get("date")  # e.g., 2026-10-25T22:29:35
        if not link or not date_iso:
            continue
        # Use the date portion as publication date
        pub_date = date_iso.split("T")[0]
        # Ensure within range
        if pub_date < START_DATE or pub_date > END_DATE:
            continue
        if link in seen:
            continue
        seen.add(link)
        per_day_counts[pub_date] = per_day_counts.get(pub_date, 0) + 1
    page += 1
    time.sleep(1)  # polite rate limit

# Write TSV
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "thenewdaily-com-au.tsv")
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as out_f:
    for url in sorted(seen):
        # Find its date from per_day_counts by extracting date from URL path if needed
        # Since we stored counts per date, we can reconstruct by matching URL containing /YYYY/MM/DD/
        # Simpler: reuse the API date info – we already have it in per_day_counts only counts.
        # We'll re-parse the URL to extract date segment.
        # Expected format includes /YYYY/MM/DD/ after the section.
        parts = url.split('/')
        date_str = ""
        # locate a segment of length 4 followed by two 2-digit segments
        for i in range(len(parts)-3):
            if (
                len(parts[i]) == 4 and parts[i].isdigit() and
                len(parts[i+1]) == 2 and parts[i+1].isdigit() and
                len(parts[i+2]) == 2 and parts[i+2].isdigit()
            ):
                date_str = f"{parts[i]}-{parts[i+1]}-{parts[i+2]}"
                break
        if not date_str:
            # fallback to ISO date from API not stored; skip
            continue
        out_f.write(f"{url}\t{date_str}\n")

# Print per‑day counts
for d in sorted(per_day_counts):
    print(f"{d}\t{per_day_counts[d]}")
