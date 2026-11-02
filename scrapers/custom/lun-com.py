#!/usr/bin/env python3
"""Scrape article page URLs from Las Últimas Noticias (lun.com).
import os, sys
print('Running script, __file__ =', __file__)

Approach:
- The site provides date‑based newspaper pages via the endpoint
  ``/Pages/NewsDetail.aspx`` with query parameters:
    dt=YYYY-MM-DD   (date)
    SupplementId=0 (kept constant)
    PaginaId=N     (page number, starting at 1)
    EsAviso=0      (kept constant)
- For each date in the target window we iterate page numbers until the
  request no longer returns HTTP 200 (typically a 404). Each successful
  page URL is recorded with its date.
- All HTTP requests are performed with ``polite_fetch.fetch`` which
  respects ``robots.txt`` and rate‑limits.
- Results are written to ``data/urls_custom/lun-com.tsv`` as
  ``URL<TAB>YYYY-MM-DD`` (no header) and per‑day URL counts are printed.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path for polite_fetch import
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))

from polite_fetch import fetch

OUT_TSV = ROOT / "data" / "urls_custom" / "lun-com.tsv"
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)  # inclusive

def date_range(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

def fetch_page(url):
    status, text, _ = fetch(url)
    return status, text

def main():
    records = []  # list of (url, date_str)
    daily_counts = {}
    for dt in date_range(START, END):
        date_str = dt.strftime("%Y-%m-%d")
        page = 1
        while True:
            query = (
                f"https://www.lun.com/Pages/NewsDetail.aspx?dt={date_str}"
                f"&SupplementId=0&PaginaId={page}&EsAviso=0"
            )
            status, _ = fetch_page(query)
            if status != 200:
                # stop when first non‑200 (usually 404) is hit
                break
            records.append((query, date_str))
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            page += 1
        # optional progress output per date
        print(f"{date_str}: {daily_counts.get(date_str,0)} pages")

    # write TSV
    with OUT_TSV.open("w", encoding="utf-8") as f:
        for url, d in records:
            f.write(f"{url}\t{d}\n")
    # final summary
    total = len(records)
    print(f"Total pages collected: {total}")
    # per‑day summary sorted
    for d in sorted(daily_counts):
        print(f"{d}\t{daily_counts[d]}")

if __name__ == "__main__":
    main()
