#!/usr/bin/env python3

import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

SITEMAP_URL = 'https://andina.pe/agencia/news-sitemap.xml'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'andina-pe.tsv'))

START = date(2026, 9, 25)
END = date(2026, 10, 25)

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch sitemap {url}: HTTP {status}')
    return text

def parse_sitemap(xml_text):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is None:
            pub_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or pub_el is None:
            continue
        url = loc_el.text.strip()
        pub_dt = datetime.fromisoformat(pub_el.text.strip())
        pub_date = pub_dt.date()
        if START <= pub_date <= END:
            entries.append((url, pub_date.isoformat()))
    return entries

def write_tsv(entries):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    seen = set()
    uniq = []
    for url, d in entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, d))
    uniq.sort(key=lambda x: (x[1], x[0]))
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, d in uniq:
            f.write(f"{url}\t{d}\n")
    return uniq

def report_counts(entries):
    counts = {}
    for _, d in entries:
        counts[d] = counts.get(d, 0) + 1
    for single_date in (START + timedelta(days=i) for i in range((END-START).days + 1)):
        day_str = single_date.isoformat()
        print(f"{day_str}: {counts.get(day_str, 0)} URLs")

def main():
    try:
        index_xml = fetch_sitemap('https://andina.pe/agencia/sitemap.xml')
    except Exception as e:
        print('Error fetching sitemap index:', e, file=sys.stderr)
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(index_xml)
    sitemap_urls = [elem.text.strip() for elem in root.findall('ns:sitemap/ns:loc', ns)]
    if SITEMAP_URL not in sitemap_urls:
        sitemap_urls.append(SITEMAP_URL)
    all_entries = []
    for sm_url in sitemap_urls:
        try:
            xml = fetch_sitemap(sm_url)
            entries = parse_sitemap(xml)
            all_entries.extend(entries)
        except Exception as e:
            print(f'Warning: could not process sitemap {sm_url}: {e}', file=sys.stderr)
    uniq = write_tsv(all_entries)
    report_counts(uniq)
    print(f"Wrote {len(uniq)} unique URLs to {OUTPUT_TSV}")

if __name__ == '__main__':
    main()
