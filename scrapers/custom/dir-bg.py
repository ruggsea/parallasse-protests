import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch module not found\n')
    sys.exit(1)

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

# Sitemaps for the months covering the range
SITEMAP_URLS = [
    f'https://dnes.dir.bg/sitemaps/2026/{m}/news.xml'
    for m in ('9', '10')
]

entries = []  # list of (url, date_str)
seen = set()

for sitemap_url in SITEMAP_URLS:
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch sitemap {sitemap_url}: {status}\n')
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        sys.stderr.write(f'XML parse error for {sitemap_url}: {e}\n')
        continue
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        lastmod = lastmod_el.text.strip()
        # Parse date part
        try:
            dt = datetime.datetime.fromisoformat(lastmod)
        except ValueError:
            # fallback to date only
            try:
                dt = datetime.datetime.strptime(lastmod, '%Y-%m-%d')
            except ValueError:
                continue
        date = dt.date()
        if date < START_DATE or date > END_DATE:
            continue
        if url in seen:
            continue
        seen.add(url)
        entries.append((url, date.isoformat()))

# Write TSV
output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'dir-bg.tsv'))
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    for url, d in entries:
        f.write(f"{url}\t{d}\n")

# Print per‑day counts
counts = defaultdict(int)
for _, d in entries:
    counts[d] += 1
for day in sorted(counts):
    print(f"{day}: {counts[day]} URLs")
