#!/usr/bin/env python3
import sys, os, re, csv
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Add the scrapers root to sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://www.journaldemontreal.com'
SITEMAP_INDEX = f'{BASE_URL}/sitemap.xml'
START_DATE = datetime(2026, 9, 25)
END_DATE = datetime(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'journaldemontreal-com.tsv'))

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {url} status {status}', file=sys.stderr)
        return None
    return text

def parse_sitemap(url):
    txt = fetch_text(url)
    if not txt:
        return []
    try:
        root = ET.fromstring(txt)
    except ET.ParseError as e:
        print(f'XML parse error {url}: {e}', file=sys.stderr)
        return []
    ns = {'ns': 'https://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = []
    for loc in root.findall('.//ns:loc', ns):
        urls.append(loc.text.strip())
    return urls

def extract_date_from_path(url):
    # URLs are like https://www.journaldemontreal.com/2026/10/25/slug
    m = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None

def main():
    # Step 1: get list of article sitemap files
    sitemap_urls = []
    index_txt = fetch_text(SITEMAP_INDEX)
    if not index_txt:
        sys.exit(1)
    try:
        idx_root = ET.fromstring(index_txt)
    except ET.ParseError as e:
        print(f'Failed to parse sitemap index: {e}', file=sys.stderr)
        sys.exit(1)
    ns = {'ns': 'https://www.sitemaps.org/schemas/sitemap/0.9'}
    for loc in idx_root.findall('.//ns:loc', ns):
        loc_text = loc.text.strip()
        if re.search(r'sitemap-articles-\d+\.xml$', loc_text):
            sitemap_urls.append(loc_text)
    # Collect URLs
    collected = {}
    for sm_url in sitemap_urls:
        for article_url in parse_sitemap(sm_url):
            pub_date = extract_date_from_path(article_url)
            if not pub_date:
                continue
            if START_DATE <= pub_date <= END_DATE:
                collected[article_url] = pub_date.date()
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, d in sorted(collected.items()):
            writer.writerow([url, d.isoformat()])
    # Print per‑day counts
    counts = {}
    for d in collected.values():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f'{day}: {counts[day]}')

if __name__ == '__main__':
    main()
