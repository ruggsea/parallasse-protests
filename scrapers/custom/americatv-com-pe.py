#!/usr/bin/env python3
import os, sys, csv
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Add scraper path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.strptime('2026-09-25', '%Y-%m-%d').date()
END = datetime.strptime('2026-10-25', '%Y-%m-%d').date()

SITEMAP_URLS = [
    'https://www.americatv.com.pe/sitemap/news?ns_source=organico',
    'https://www.americatv.com.pe/noticias/sitemap/news?ns_source=organico',
]

def main():
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    urls = []
    seen = set()
    for sitemap_url in SITEMAP_URLS:
        status, text, _ = fetch(sitemap_url)
        if status != 200:
            print(f'Failed to fetch sitemap {sitemap_url}, status {status}', file=sys.stderr)
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            print(f'XML parse error for {sitemap_url}: {e}', file=sys.stderr)
            continue
        for url_el in root.findall('ns:url', ns):
            loc_el = url_el.find('ns:loc', ns)
            date_el = url_el.find('news:news/news:publication_date', ns)
            if loc_el is None or date_el is None:
                continue
            loc = loc_el.text.strip()
            pub_date = date_el.text.strip()[:10]
            try:
                pub = datetime.strptime(pub_date, '%Y-%m-%d').date()
            except ValueError:
                continue
            if START <= pub <= END and loc not in seen:
                seen.add(loc)
                urls.append((loc, pub_date))
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'americatv-com-pe.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for loc, pub_date in sorted(urls, key=lambda x: x[1]):
            writer.writerow([loc, pub_date])
    # Print per‑day counts
    counts = {}
    for _, d in urls:
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f'{day}\t{counts[day]}')
if __name__ == '__main__':
    main()
