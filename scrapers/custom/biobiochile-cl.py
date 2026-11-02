#!/usr/bin/env python3
import sys, os, datetime, csv
from urllib.parse import urlparse
# Ensure the fetch module is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# The fetch module resides at scrapers (project root) per instruction
# but we add parent of scrapers to path; adjust if needed
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

# Using static monthly sitemaps as they contain recent URLs
SITEMAP_URL_TEMPLATE = 'https://www.biobiochile.cl/static/sitemap-{year}-{month:02d}.xml'
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/biobiochile-cl.tsv'))

def iso_to_date(iso_str: str) -> datetime.date:
    # iso format like 2025-07-22T16:26:36+00:00
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    except Exception:
        # fallback split
        dt = datetime.datetime.strptime(iso_str[:10], '%Y-%m-%d')
    return dt.date()

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap {url}: status {status}', file=sys.stderr)
        sys.exit(1)
    return text

def parse_sitemap(xml_text: str):
    import xml.etree.ElementTree as ET
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Prefer date from URL path /YYYY/MM/DD/ if present
        try:
            parts = url.split('/')
            year = int(parts[-4])
            month = int(parts[-3])
            day = int(parts[-2])
            pub_date = datetime.date(year, month, day)
        except Exception:
            # fallback to lastmod if available
            if lastmod_el is not None:
                pub_date = iso_to_date(lastmod_el.text.strip())
            else:
                continue
        yield url, pub_date

def main():
    entries = []
    # fetch both September and October sitemaps
    for year, month in [(2026, 9), (2026, 10)]:
        sitemap_url = SITEMAP_URL_TEMPLATE.format(year=year, month=month)
        try:
            sitemap_xml = fetch_sitemap(sitemap_url)
        except SystemExit:
            print(f'Skipping missing sitemap {sitemap_url}', file=sys.stderr)
            continue
        for url, pub_date in parse_sitemap(sitemap_xml):
            if START_DATE <= pub_date <= END_DATE:
                entries.append((url, pub_date))
    # dedupe
    unique = {}
    for url, pub_date in entries:
        unique[url] = pub_date
    # sort by date then url
    sorted_items = sorted(unique.items(), key=lambda x: (x[1], x[0]))
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        for url, pub_date in sorted_items:
            w.writerow([url, pub_date.isoformat()])
    # print per-day counts
    from collections import Counter
    cnt = Counter([d.isoformat() for _, d in sorted_items])
    for day in sorted(cnt):
        print(f'{day}\t{cnt[day]}')
    print(f'Wrote {len(sorted_items)} URLs to {OUTPUT_TSV}')

if __name__ == '__main__':
    main()
