#!/usr/bin/env python3
import sys, json, os, datetime, time
from pathlib import Path
# Add scrapers path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    print('polite_fetch not available:', e)
    sys.exit(1)

BASE_URL = 'https://theeastafrican.co.ke'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = Path(__file__).parents[2] / 'data' / 'urls_custom' / 'theeastafrican-co-ke.tsv'

# Placeholder: try Wayback CDX API
CDX_URL = ('https://web.archive.org/cdx/search/cdx?url=%s/*&from=%s&to=%s'
           '&output=json&fl=original,timestamp&collapse=urlkey') % (BASE_URL,
           START.strftime('%Y%m%d'), END.strftime('%Y%m%d'))

status, text, _ = fetch(CDX_URL)
if status != 200:
    print('Failed to fetch CDX:', status)
    sys.exit(1)

records = json.loads(text)
# First line is header
records = records[1:]
results = []
for url, ts in records:
    # timestamp format YYYYMMDDhhmmss
    try:
        dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S').date()
    except Exception:
        continue
    if START <= dt <= END:
        results.append((url, dt.isoformat()))

# Deduplicate
unique = {}
for u, d in results:
    unique[u] = d

OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_TSV.open('w', encoding='utf-8') as f:
    for u, d in sorted(unique.items()):
        f.write(f"{u}\t{d}\n")

print('Wrote', len(unique), 'unique URLs to', OUT_TSV)
