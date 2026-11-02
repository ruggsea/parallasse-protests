#!/usr/bin/env python3
"""Scrape article URLs from Midi Madagasikara for 2026-09-25 to 2026-10-25.
Uses Wayback CDX as fallback because site blocks direct fetches.
Writes TSV with URL and YYYY-MM-DD (date from CDX timestamp).
"""
import sys, os, json, time, datetime
from pathlib import Path

# Add scraper root to path for polite_fetch
ROOT = Path(__file__).resolve().parents[2]  # .
sys.path.insert(0, str(ROOT / 'scrapers'))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = ROOT / 'data' / 'urls_custom' / 'midi-madagasikara-mg.tsv'
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

def dates_range(start, end):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)

seen = set()
rows = []
for day in dates_range(START, END):
    ymd = day.strftime('%Y%m%d')
    # Wayback CDX for this day
    url = (
        f"https://web.archive.org/cdx/search/cdx?url=midi-madagasikara.mg/*&from={ymd}&to={ymd}&output=json&collapse=urlkey"
    )
    # retry up to 3 times
    for attempt in range(3):
        status, text, _ = fetch(url)
        if status == 200 and text:
            break
        time.sleep(2 ** attempt)
    else:
        # failed, skip day
        continue
    try:
        data = json.loads(text)
    except Exception:
        continue
    # first entry is header
    for entry in data[1:]:
        # CDX fields: urlkey, timestamp, original, mime, statuscode, digest, length
        # ensure enough fields
        if len(entry) < 3:
            continue
        original = entry[2]
        ts = entry[1]  # YYYYMMDDhhmmss
        date_part = ts[:8]
        # verify date matches day
        if date_part != ymd:
            continue
        if original not in seen:
            seen.add(original)
            rows.append((original, day.isoformat()))
    # polite pause
    time.sleep(1)

# Write TSV
with OUT_TSV.open('w', encoding='utf-8') as f:
    for url, date_str in rows:
        f.write(f"{url}\t{date_str}\n")

# Report counts per day of interest
for target in [datetime.date(2026,9,30), datetime.date(2026,10,10), datetime.date(2026,10,20)]:
    cnt = sum(1 for _, d in rows if d == target.isoformat())
    print(f"{target}: {cnt} URLs")
