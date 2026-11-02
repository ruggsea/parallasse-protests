#!/usr/bin/env python3

"""Scraper for 24 Часа (24chasa.bg)
Collect article URLs published between 2026-09-25 and 2026-10-25.
Uses the site’s Google News sitemap (https://www.24chasa.bg/sitemap.xml) which includes
<news:publication_date> for each URL.
Outputs TSV at data/urls_custom/24chasa-bg.tsv with columns:
    URL<TAB>YYYY-MM-DD
No header, one line per unique URL.
"""
import sys
import os
import datetime as dt
import time

# Ensure the project’s scraper helpers are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from polite_fetch import fetch

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)

ARCHIVE_URL_TEMPLATE = "https://www.24chasa.bg/archivio/{year:04d}/{month:02d}/{day:02d}"

def fetch_day_archive(date: dt.date):
    url = ARCHIVE_URL_TEMPLATE.format(year=date.year, month=date.month, day=date.day)
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch archive {date} (HTTP {status})", file=sys.stderr)
        return None
    return text

def extract_urls(html: str):
    # Simple regex to find article URLs of the form /<section>/article/<id>
    import re
    pattern = re.compile(r"https?://www\.24chasa\.bg/[^/]+/article/\d+", re.IGNORECASE)
    return set(pattern.findall(html))

def collect_urls():
    per_day = {}
    cur = START
    one_day = dt.timedelta(days=1)
    while cur <= END:
        html = fetch_day_archive(cur)
        if html:
            urls = extract_urls(html)
            if urls:
                per_day[cur] = urls
                print(f"{cur}: {len(urls)} URLs")
            else:
                print(f"{cur}: no article URLs found", file=sys.stderr)
        else:
            print(f"{cur}: fetch error", file=sys.stderr)
        # Polite pause – the fetch helper already respects crawl‑delay, but a tiny sleep avoids hammering
        time.sleep(0.2)
        cur += one_day
    return per_day

def write_tsv(per_day):
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "24chasa-bg.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for day in sorted(per_day):
            for url in sorted(per_day[day]):
                f.write(f"{url}\t{day.isoformat()}\n")
                total += 1
    print(f"Total URLs written: {total}")

def main():
    per_day = collect_urls()
    if not per_day:
        print("No URLs collected in the date range.", file=sys.stderr)
        sys.exit(1)
    write_tsv(per_day)

if __name__ == "__main__":
    main()
