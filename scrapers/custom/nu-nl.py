#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
SITEMAP = 'https://www.nu.nl/sitemap_news.xml'

status, text, _ = fetch(SITEMAP)
if status != 200:
    print(f'Failed to fetch sitemap: {status}')
    sys.exit(1)

# Parse XML; we look for <url><loc> and <news:publication_date>
ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
urls = []
root = ET.fromstring(text)
ns = {
    's': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}
urls = []
for url_elem in root.findall('s:url', ns):
    loc = url_elem.findtext('s:loc', namespaces=ns)
    pub_date_elem = url_elem.find('news:news/news:publication_date', namespaces=ns)
    if loc and pub_date_elem is not None:
        # publication_date like 2026-10-24T20:34:53+02:00
        try:
            dt = datetime.datetime.fromisoformat(pub_date_elem.text)
        except Exception:
            continue
        d = dt.date()
        if START <= d <= END:
            urls.append((loc, d.isoformat()))

# Deduplicate preserving order
seen = set()
unique = []
for u, d in urls:
    if u not in seen:
        seen.add(u)
        unique.append((u, d))

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'nu-nl.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for u, d in unique:
        f.write(f"{u}\t{d}\n")

# Summary per day
from collections import Counter
counter = Counter(d for _, d in unique)
for day in sorted(counter):
    print(f"{day}: {counter[day]} URLs")
print(f"Total URLs: {len(unique)}")
