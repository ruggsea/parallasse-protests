#!/usr/bin/env python3
import sys, os, csv
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET

# Insert path for polite_fetch (as per project conventions)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# The repository root is two levels up from scrapers/custom
# Import fetch function
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch import failed', file=sys.stderr)
    sys.exit(1)

START = date(2026, 9, 25)
END = date(2026, 10, 25)
SITEMAP_URL = 'https://www.thejournal.ie/sitemaps/sitemap.xml'

resp = fetch(SITEMAP_URL)
if hasattr(resp, 'status_code'):
    status = resp.status_code
    text = resp.text
else:
    status, text, _ = resp
if status != 200:
    print(f'Failed to fetch sitemap: HTTP {status}', file=sys.stderr)
    sys.exit(1)

# Parse XML with namespaces
ns = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}
root = ET.fromstring(text)
urls_by_date = {}
for url_el in root.findall('ns:url', ns):
    loc_el = url_el.find('ns:loc', ns)
    news_el = url_el.find('news:news', ns)
    if loc_el is None or news_el is None:
        continue
    pub_el = news_el.find('news:publication_date', ns)
    if pub_el is None:
        continue
    url = loc_el.text.strip()
    pub_dt = pub_el.text.strip()
    # publication_date is ISO with time and offset, extract date part
    try:
        pub_date = datetime.fromisoformat(pub_dt).date()
    except Exception:
        # fallback split
        pub_date = datetime.strptime(pub_dt.split('T')[0], '%Y-%m-%d').date()
    if START <= pub_date <= END:
        urls_by_date.setdefault(pub_date, set()).add(url)

# Ensure output directory exists
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thejournal-ie.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

with open(out_path, 'w', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    for dt in sorted(urls_by_date):
        for u in sorted(urls_by_date[dt]):
            writer.writerow([u, dt.isoformat()])

# Print summary per day
print('Summary:')
current = START
while current <= END:
    count = len(urls_by_date.get(current, []))
    print(f'{current.isoformat()}: {count} URLs')
    current += timedelta(days=1)
