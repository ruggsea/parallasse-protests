#!/usr/bin/env python3
import sys, os, gzip, itertools
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://www.vistazo.com'
MEGASITEMAP_INDEX = f'{BASE_URL}/megasitemap.xml'
SITEMAP_FOR_GOOGLE = f'{BASE_URL}/sitemapforgoogle.xml'
START = datetime(2026, 9, 25).date()
END = datetime(2026, 10, 25).date()
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'vistazo-com.tsv'))

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {status} fetching {url}', file=sys.stderr)
        return None
    return text

def parse_sitemap_index(xml_text):
    root = ET.fromstring(xml_text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for sitemap in root.findall('sm:sitemap', ns):
        loc = sitemap.find('sm:loc', ns)
        if loc is not None and loc.text:
            yield loc.text.strip()

def parse_news_sitemap(xml_text):
    root = ET.fromstring(xml_text)
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or pub_el is None:
            continue
        url = loc_el.text.strip()
        pub = pub_el.text.strip()
        try:
            pub_dt = datetime.fromisoformat(pub)
        except Exception:
            continue
        if START <= pub_dt.date() <= END:
            yield url, pub_dt.date().isoformat()

def main():
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    # Step 1: fetch megasitemap index and the Google news sitemap
    idx_text = fetch_text(MEGASITEMAP_INDEX)
    if not idx_text:
        sys.exit(1)
    sitemap_urls = list(parse_sitemap_index(idx_text))
    # Add the Google news sitemap directly
    sitemap_urls.append(SITEMAP_FOR_GOOGLE)

    all_entries = []
    for sm_url in sitemap_urls:
        sm_text = fetch_text(sm_url)
        if not sm_text:
            continue
        all_entries.extend(parse_news_sitemap(sm_text))

    if not all_entries:
        print('No entries in any sitemap within date range', file=sys.stderr)
    # Deduplicate
    seen = set()
    with open(OUT_TSV, 'w', encoding='utf-8') as out:
        for url, date_str in all_entries:
            if url in seen:
                continue
            seen.add(url)
            out.write(f"{url}\t{date_str}\n")
    # Reporting per day counts
    counts = {}
    for _, date_str in all_entries:
        counts[date_str] = counts.get(date_str, 0) + 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")

if __name__ == '__main__':
    main()
