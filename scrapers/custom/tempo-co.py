#!/usr/bin/env python3
"""Scraper for Tempo.co articles between 2026-09-25 and 2026-10-25.
Uses polite_fetch for all HTTP requests.
Attempts Wayback CDX API; if unavailable, logs and exits.
Writes TSV with URL and date (date extracted from snapshot timestamp).
"""
import sys, json, os, datetime, pathlib

# Ensure script can be run from project root
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scrapers'))
from polite_fetch import fetch

OUT_TSV = ROOT / 'data' / 'urls_custom' / 'tempo-co.tsv'
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

CDX_URL = (
    'https://web.archive.org/cdx/search/cdx?url=tempo.co/*'
    f'&from={START.strftime("%Y%m%d")}'
    f'&to={END.strftime("%Y%m%d")}'
    '&output=json&collapse=urlkey&filter=mimetype:text/html'
)

status, txt, _ = fetch(CDX_URL)
if status != 200:
    # try without filter parameter
    alt_url = CDX_URL.replace('&filter=mimetype:text/html','')
    status, txt, _ = fetch(alt_url)
if status != 200:
    sys.stderr.write(f"Failed to fetch CDX (both attempts): HTTP {status}\n")
    sys.exit(1)

entries = json.loads(txt)
# entries[0] is header row
header = entries[0]
url_idx = header.index('url')
timestamp_idx = header.index('timestamp')

seen = set()
with OUT_TSV.open('w', encoding='utf-8') as out:
    for row in entries[1:]:
        url = row[url_idx]
        ts = row[timestamp_idx]
        # timestamp format: YYYYMMDDhhmmss
        try:
            date = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S").date()
        except Exception:
            continue
        if not (START <= date <= END):
            continue
        full_url = f"https://www.tempo.co{url}" if url.startswith('/') else url
        if full_url in seen:
            continue
        seen.add(full_url)
        out.write(f"{full_url}\t{date.isoformat()}\n")

print(f"Wrote {len(seen)} URLs to {OUT_TSV}")