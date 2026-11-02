#!/usr/bin/env python3
"""Scrape article URLs from BSS (bss.org.bd) for 2026-09-25 to 2026-10-25.
Uses Wayback CDX as source (robots.txt does not provide a sitemap).
Writes TSV with URL<TAB>YYYY-MM-DD to data/urls_custom/bss-org-bd.tsv.
Prints count per day.
"""
import sys, json, datetime, os
from urllib.parse import urlparse

# Add the repository root to sys.path so polite_fetch can be imported
script_dir = os.path.abspath(os.path.dirname(__file__))
# Add the scrapers directory (which contains polite_fetch) to sys.path
sys.path.insert(0, os.path.join(script_dir, '..'))

try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not available', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

# Wayback CDX request (JSON output, collapse duplicate URLs)
cdx_url = (
    'https://web.archive.org/cdx/search/cdx?'
    f'url=http://bss.org.bd/*&from=20260925&to=20261025&output=json&collapse=urlkey'
)
import subprocess, shlex
# Use curl directly for Wayback CDX (external domain)
result = subprocess.run(['curl', '-s', cdx_url], capture_output=True, text=True)
if result.returncode != 0:
    print('curl failed', file=sys.stderr)
    sys.exit(1)
records = json.loads(result.stdout)
if not records:
    print('No CDX records returned', file=sys.stderr)
    sys.exit(1)
header = records[0]
idx_original = header.index('original') if 'original' in header else 2
idx_timestamp = header.index('timestamp') if 'timestamp' in header else 1

url_date = {}
for row in records[1:]:
    url = row[idx_original]
    ts = row[idx_timestamp]  # format YYYYMMDDhhmmss
    try:
        dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S')
    except ValueError:
        continue
    date = dt.date()
    if not (START <= date <= END):
        continue
    # Use the date from the capture as a fallback publication date
    url_date[url] = date

# Deduplicate URLs (already collapsed), now write TSV
out_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'data', 'urls_custom', 'bss-org-bd.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date in sorted(url_date.items()):
        f.write(f"{url}\t{date.isoformat()}\n")

# Print per‑day counts
counts = {}
for d in url_date.values():
    counts.setdefault(d, 0)
    counts[d] += 1
for d in sorted(counts):
    print(f"{d}: {counts[d]} URLs")
