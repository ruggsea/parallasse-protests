#!/usr/bin/env python3
"""Scrape article URLs from Junge Freiheit for 2026-09-25 to 2026-10-25.
Writes TSV with columns: URL<TAB>YYYY-MM-DD (publication date).
Uses the year sitemap (sitemap-posttype-post.2026.xml) and polite_fetch.
"""
import sys, os, datetime, xml.etree.ElementTree as ET

# Add path for polite_fetch (project's scrapers folder)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

SITEMAP_URL = 'https://jungefreiheit.de/sitemap-posttype-post.2026.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

status, text, _ = fetch(SITEMAP_URL)
if status != 200:
    print(f'Failed to fetch sitemap: {status}')
    sys.exit(1)

# Parse XML
root = ET.fromstring(text)
ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
# The sitemap does not declare a namespace prefix, so we can ignore.

urls_by_date = {}
seen = set()

ns_uri = 'http://www.sitemaps.org/schemas/sitemap/0.9'
for url_el in root.findall(f'.//{{{ns_uri}}}url'):
    loc_el = url_el.find(f'{{{ns_uri}}}loc')
    if loc_el is None or not loc_el.text:
        continue
    url = loc_el.text.strip()
    if url in seen:
        continue
    seen.add(url)
    # Try lastmod first
    date_str = None
    lastmod_el = url_el.find(f'{{{ns_uri}}}lastmod')
    if lastmod_el is not None and lastmod_el.text:
        # Example: 2026-10-25T18:15:11+01:00
        dt = lastmod_el.text.split('T')[0]
        date_str = dt
    else:
        # fallback: extract date from URL path /YYYY/MM/DD/
        parts = url.split('/')
        # find a 4-digit year segment
        for i, part in enumerate(parts):
            if len(part) == 4 and part.isdigit():
                try:
                    yr = int(part)
                    mo = int(parts[i+1])
                    da = int(parts[i+2])
                    date_str = f"{yr:04d}-{mo:02d}-{da:02d}"
                except Exception:
                    pass
                break
    if not date_str:
        continue
    try:
        pub_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        continue
    if not (START <= pub_date <= END):
        continue
    urls_by_date.setdefault(pub_date, []).append(url)

# Write TSV
print(f"Collected {sum(len(v) for v in urls_by_date.values())} URLs")
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'jungefreiheit-de.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for day in sorted(urls_by_date):
        for u in sorted(urls_by_date[day]):
            f.write(f"{u}\t{day.isoformat()}\n")

# Print per‑day counts
for day in sorted(urls_by_date):
    print(f"{day}: {len(urls_by_date[day])} URLs")
