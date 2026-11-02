#!/usr/bin/env python3
"""Scrape article URLs from eguur.mn within a date range.

Output: data/urls_custom/eguur-mn.tsv with lines:
    URL<TAB>YYYY-MM-DD
No header, unique URLs.
"""
import sys
import os
import json
import time
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

# Date range (inclusive)
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S')

base_url = 'https://eguur.mn/wp-json/wp/v2/posts'
per_page = 100
page = 1
all_entries = {}

while True:
    params = (
        f'?per_page={per_page}&_fields=link,date'
        f'&after={iso(START)}&before={iso(END + timedelta(days=1))}'
        f'&page={page}'
    )
    url = base_url + params
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed request {url}: status {status}')
        break
    try:
        posts = json.loads(text)
    except json.JSONDecodeError:
        print('JSON decode error')
        break
    if not posts:
        break
    for p in posts:
        link = p.get('link')
        date_iso = p.get('date')  # e.g., 2026-10-26T17:10:20
        if not link or not date_iso:
            continue
        date_part = date_iso.split('T')[0]
        # Verify within range
        try:
            d = datetime.strptime(date_part, '%Y-%m-%d')
        except ValueError:
            continue
        if START <= d <= END:
            all_entries[link] = date_part
    page += 1
    time.sleep(0.5)  # be polite

# Write output
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'eguur-mn.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date in sorted(all_entries.items()):
        f.write(f"{url}\t{date}\n")

# Print per‑day counts for quick check
counts = {}
for d in all_entries.values():
    counts[d] = counts.get(d, 0) + 1
print('Total URLs:', len(all_entries))
for day in sorted(counts)[:5]:
    print(day, counts[day])
