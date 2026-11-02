#!/usr/bin/env python3
import re, sys, json, os, datetime
from urllib.parse import urljoin

# Ensure polite_fetch in path (relative to repo root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = 'https://presstv.ir'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/presstv-ir.tsv'))
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def date_in_range(d):
    return START <= d <= END

def fetch_wayback():
    cdx_url = (
        f'http://web.archive.org/cdx/search/cdx?url={BASE}/Detail/*'
        f'&from=20260925&to=20261025&output=json&collapse=urlkey&fl=original,timestamp'
    )
    status, text, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    rows = data[1:]
    out = []
    for original, ts in rows:
        try:
            dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S').date()
        except Exception:
            continue
        if date_in_range(dt):
            out.append((original, dt.isoformat()))
    return out

def scrape_home():
    status, text, _ = fetch(BASE)
    if status != 200:
        return []
    # Matches href optional quotes, captures /Detail/YYYY/MM/DD/... and extracts date parts
    pattern = re.compile(r'href\s*=\s*["\']?(/Detail/(\d{4})/(\d{2})/(\d{2})/[^"\'>\s]+)["\']?', re.IGNORECASE)
    out = []
    for m in pattern.finditer(text):
        path = m.group(1)
        y, mth, d = map(int, m.group(2,3,4))
        try:
            dt = datetime.date(y, mth, d)
        except Exception:
            continue
        if date_in_range(dt):
            out.append((urljoin(BASE, path), dt.isoformat()))
    return out

entries = fetch_wayback()
if not entries:
    entries = scrape_home()
# Deduplicate preserving order
seen = set()
unique = []
for url, date in entries:
    if url not in seen:
        seen.add(url)
        unique.append((url, date))

os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
with open(OUT_TSV, 'w', encoding='utf-8') as f:
    for url, date in unique:
        f.write(f"{url}\t{date}\n")

# Report per‑day counts (simple stdout)
from collections import Counter
cnt = Counter(date for _, date in unique)
for day in sorted(cnt):
    print(f"{day}: {cnt[day]} URLs")
print(f"Total URLs: {len(unique)}")
