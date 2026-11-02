import sys, os, csv
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Add polite_fetch to path
base_dir = os.path.dirname(os.path.abspath(__file__))
scrapers_dir = os.path.abspath(os.path.join(base_dir, '..'))
sys.path.insert(0, scrapers_dir)
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found in scrapers directory')

START = datetime.strptime('2026-09-25', '%Y-%m-%d')
END = datetime.strptime('2026-10-25', '%Y-%m-%d')

SITEMAP_URL = 'https://news.tvbs.com.tw/sitemap/news-sitemap'

status, text, _ = fetch(SITEMAP_URL)
if status != 200:
    raise RuntimeError(f'Failed to fetch sitemap: {status}')

ns = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9',
}

root = ET.fromstring(text)

records = []
for url_el in root.findall('ns:url', ns):
    loc = url_el.findtext('ns:loc', namespaces=ns)
    pub_date_el = url_el.find('news:news/news:publication_date', ns)
    if not loc or pub_date_el is None:
        continue
    pub_dt = datetime.fromisoformat(pub_date_el.text.rstrip('Z'))
    pub_date = pub_dt.date()
    if START.date() <= pub_date <= END.date():
        records.append((loc, pub_date.isoformat()))

# Deduplicate
unique = {}
for url, date_str in records:
    unique[url] = date_str

project_root = os.path.abspath(os.path.join(base_dir, '..', '..'))
out_path = os.path.join(project_root, 'data', 'urls_custom', 'tvbs-com-tw.tsv')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date_str in sorted(unique.items()):
        f.write(f"{url}\t{date_str}\n")

# Print counts per day
counts = {}
for date_str in unique.values():
    counts[date_str] = counts.get(date_str, 0) + 1
for d in sorted(counts):
    print(f"{d}\t{counts[d]}")
