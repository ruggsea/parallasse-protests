#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Add scrapers dir to sys.path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not available')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
SITEMAP = 'https://novayagazeta.ru/feed/sitemap'

status, text, _ = fetch(SITEMAP)
if status != 200:
    print(f'Failed to fetch sitemap, status {status}')
    sys.exit(1)

root = ET.fromstring(text)
entries = []
for url in root.findall('.//url'):
    loc = url.find('loc')
    lastmod = url.find('lastmod')
    if loc is None or lastmod is None:
        continue
    url_str = loc.text.strip()
    lm_str = lastmod.text.strip()
    # parse date portion
    try:
        dt = datetime.datetime.fromisoformat(lm_str.replace('Z', '+00:00'))
    except Exception:
        continue
    d = dt.date()
    if START <= d <= END:
        entries.append((d, url_str))

# deduplicate by URL, keep earliest date if multiple
unique = {}
for d, u in entries:
    if u not in unique or d < unique[u]:
        unique[u] = d

# group by date for reporting
by_date = {}
for u, d in unique.items():
    by_date.setdefault(d, []).append(u)

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'novayagazeta-ru.tsv')
)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for d in sorted(by_date):
        for u in sorted(by_date[d]):
            f.write(f"{u}\t{d.isoformat()}\n")

# print summary
for d in sorted(by_date):
    print(f"{d.isoformat()}: {len(by_date[d])} URLs")
print(f"Total {len(unique)} unique URLs written to {out_path}")
