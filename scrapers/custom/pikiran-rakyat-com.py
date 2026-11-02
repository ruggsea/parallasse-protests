#!/usr/bin/env python3
import sys, os, json, datetime, collections, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = 'https://www.pikiran-rakyat.com'
SITEMAP_INDEX = f'{BASE}/sitemap.xml'
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)  # inclusive

output_tsv = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/pikiran-rakyat-com.tsv'))
os.makedirs(os.path.dirname(output_tsv), exist_ok=True)

seen = set()
per_day = collections.Counter()

def parse_date(dt_str):
    # dt_str like 2026-10-26T08:37:35+07:00, take date part
    return datetime.datetime.fromisoformat(dt_str.split('+')[0]).date()

# Step 1: fetch sitemap index
status, txt, _ = fetch(SITEMAP_INDEX)
if status != 200:
    sys.stderr.write(f'Failed to fetch sitemap index {SITEMAP_INDEX}: {status}\n')
    sys.exit(1)
root = ET.fromstring(txt)
# Namespace handling
ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
if root.tag.endswith('sitemapindex'):
    sitemap_urls = [elem.find('sm:loc', ns).text for elem in root.findall('sm:sitemap', ns)]
else:
    sitemap_urls = []

for sm_url in sitemap_urls:
    status, txt, _ = fetch(sm_url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch sitemap {sm_url}: {status}\n')
        continue
    try:
        sroot = ET.fromstring(txt)
    except ET.ParseError as e:
        sys.stderr.write(f'XML parse error in {sm_url}: {e}\n')
        continue
    # Determine if this is a urlset (list of urls)
    if not sroot.tag.endswith('urlset'):
        continue
    for url_elem in sroot.findall('sm:url', ns):
        loc = url_elem.find('sm:loc', ns)
        lastmod = url_elem.find('sm:lastmod', ns)
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        date = parse_date(lastmod.text.strip())
        if date < START_DATE or date > END_DATE:
            continue
        if url in seen:
            continue
        seen.add(url)
        per_day[date.isoformat()] += 1
        with open(output_tsv, 'a', encoding='utf-8') as f:
            f.write(f"{url}\t{date.isoformat()}\n")

# Summary
print('Finished scraping. Total URLs:', len(seen))
for d in sorted(per_day):
    print(d, per_day[d])
