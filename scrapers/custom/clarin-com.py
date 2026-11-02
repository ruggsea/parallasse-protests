#!/usr/bin/env python3

import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

# Configuration
BASE_SITEMAP = 'https://www.clarin.com/sitemaps/index.xml'
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'clarin-com.tsv'))

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: status {status}')
    return ET.fromstring(text.encode('utf-8'))

def parse_date(date_str):
    try:
        dt = datetime.datetime.fromisoformat(date_str.rstrip('Z'))
    except ValueError:
        dt = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d')
    return dt.date()

def main():
    urls_by_date = {}
    root = fetch_xml(BASE_SITEMAP)
    sitemap_urls = [elem.findtext('{*}loc') or elem.findtext('loc') for elem in root.findall('.//{*}sitemap')]
    if not sitemap_urls:
        sitemap_urls = [elem.findtext('loc') for elem in root.findall('sitemap')]
    for sitemap_url in sitemap_urls:
        if not sitemap_url:
            continue
        try:
            sm_root = fetch_xml(sitemap_url)
        except Exception:
            continue
        for url_el in sm_root.findall('.//{*}url'):
            loc = url_el.findtext('{*}loc') or url_el.findtext('loc')
            lastmod = url_el.findtext('{*}lastmod') or url_el.findtext('lastmod')
            if not loc or not lastmod:
                continue
            try:
                pub_date = parse_date(lastmod)
            except Exception:
                continue
            if START_DATE <= pub_date <= END_DATE:
                urls_by_date.setdefault(pub_date, set()).add(loc)
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as out:
        for pub_date in sorted(urls_by_date):
            for loc in sorted(urls_by_date[pub_date]):
                out.write(f"{loc}\t{pub_date.isoformat()}\n")
    for pub_date in sorted(urls_by_date):
        print(f"{pub_date}: {len(urls_by_date[pub_date])} URLs")

if __name__ == '__main__':
    main()
