#!/usr/bin/env python3
"""Scrape article URLs from Plan V (Ecuador) via WordPress REST API.

Outputs a TSV file at data/urls_custom/planv-com-ec.tsv with lines:
    URL<TAB>YYYY-MM-DD
Only articles published between 2026-09-25 and 2026-10-25 (inclusive) are included.
The script respects robots.txt by using the project's ``polite_fetch`` helper.
"""
import sys
import os
import json
from datetime import datetime, timedelta

# Ensure the helper is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # add scrapers directory to sys.path
# The helper lives in scrapers directory (project root/scrapers)
# ``polite_fetch`` provides ``fetch`` that returns (status, text, headers)
from polite_fetch import fetch

BASE_URL = "https://planv.com.ec"
API_ENDPOINT = f"{BASE_URL}/wp-json/wp/v2/posts"
# Date window (inclusive)
START_DATE = datetime(2026, 9, 25)
END_DATE = datetime(2026, 10, 25, 23, 59, 59)

# WP REST expects ISO8601 timestamps (UTC). The site stores dates in local time; we request a generous window.
AFTER = (START_DATE - timedelta(days=1)).isoformat()
BEFORE = (END_DATE + timedelta(days=1)).isoformat()

PER_PAGE = 100
page = 1
results = []
while True:
    url = (
        f"{API_ENDPOINT}?per_page={PER_PAGE}&_fields=link,date"
        f"&after={AFTER}&before={BEFORE}&page={page}"
    )
    status, text, _ = fetch(url)
    if status != 200:
        # Stop on any non‑200 – could be 400 when page out of range
        break
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        break
    if not items:
        break
    for item in items:
        link = item.get("link")
        date_str = item.get("date")  # local date string like "2026-09-30T12:34:56"
        if not link or not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            continue
        # Keep only items inside the exact window
        if START_DATE <= dt <= END_DATE:
            results.append((link.rstrip("/"), dt.date().isoformat()))
    page += 1
    # Safety: avoid infinite loops
    if page > 500:
        break

# Deduplicate while preserving order
seen = set()
unique = []
for link, date in results:
    if link not in seen:
        seen.add(link)
        unique.append((link, date))

# Prepare output directory
out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/urls_custom"))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "planv-com-ec.tsv")
with open(out_path, "w", encoding="utf-8") as f:
    for link, date in unique:
        f.write(f"{link}\t{date}\n")

# Print simple stats per day
from collections import Counter
counter = Counter(date for _, date in unique)
print("Collected URLs per day:")
for day in sorted(counter):
    print(f"{day}\t{counter[day]}")
print(f"Total URLs: {len(unique)} written to {out_path}")
