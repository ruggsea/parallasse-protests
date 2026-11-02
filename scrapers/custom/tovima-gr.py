#!/usr/bin/env python3

import sys
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, date

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

BASE_URL = 'https://www.tovima.gr'
SITEMAP_INDEX = f'{BASE_URL}/sitemap_index.xml'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/tovima-gr.tsv'))
START = date(2026, 9, 25)
END = date(2026, 10, 25)

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: status {status}')
    return text

def parse_sitemap_urls(sitemap_xml):
    urls = []
    root = ET.fromstring(sitemap_xml)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod = None
        if lastmod_el is not None and lastmod_el.text:
            # Take date part only
            lastmod = lastmod_el.text.strip().split('T')[0]
        urls.append((loc, lastmod))
    return urls

def date_from_url(url):
    # URLs have pattern https://www.tovima.gr/YYYY/MM/DD/...  extract date
    m = re.search(r'/([0-9]{4})/([0-9]{2})/([0-9]{2})/', url)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

def main():
    # Step 1: fetch sitemap index
    try:
        index_xml = fetch_text(SITEMAP_INDEX)
    except Exception as e:
        print(f'Error fetching sitemap index: {e}')
        sys.exit(1)
    # Find post-sitemap URLs
    root = ET.fromstring(index_xml)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = []
    for sm_el in root.findall('ns:sitemap', ns):
        loc_el = sm_el.find('ns:loc', ns)
        if loc_el is not None and 'post-sitemap' in loc_el.text:
            sitemap_urls.append(loc_el.text.strip())
    # Collect URLs
    collected = {}
    per_day_counts = defaultdict(int)
    for sm_url in sitemap_urls:
        try:
            sm_xml = fetch_text(sm_url)
        except Exception as e:
            print(f'Failed sitemap {sm_url}: {e}')
            continue
        for loc, lastmod in parse_sitemap_urls(sm_xml):
            if loc in collected:
                continue
            art_date = None
            # Prefer lastmod if available and parsable
            if lastmod:
                try:
                    art_date = datetime.strptime(lastmod, '%Y-%m-%d').date()
                except ValueError:
                    pass
            if not art_date:
                art_date = date_from_url(loc)
            if not art_date:
                continue
            if START <= art_date <= END:
                collected[loc] = art_date.isoformat()
                per_day_counts[art_date] += 1
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, d in collected.items():
            f.write(f"{url}\t{d}\n")
    # Print summary
    total = len(collected)
    print(f'Wrote {total} URLs to {OUTPUT_TSV}')
    for day in sorted(per_day_counts):
        print(f'{day}: {per_day_counts[day]}')

if __name__ == '__main__':
    main()
