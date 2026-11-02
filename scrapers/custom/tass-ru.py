#!/usr/bin/env python3
"""Scrape TASS (en.tass.ru / tass.com) article URLs for a date window.
Outputs TSV of URL<TAB>YYYY-MM-DD to data/urls_custom/tass-ru.tsv.
Uses polite_fetch for all HTTP requests.
"""
import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# The repository root contains scrapers/ with polite_fetch.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date(dt_str: str) -> datetime.date:
    # dt_str like '2026-10-25T11:31:10+03:00'
    try:
        date_part = dt_str.split('T')[0]
        return datetime.datetime.strptime(date_part, '%Y-%m-%d').date()
    except Exception:
        return None

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"Failed to fetch sitemap {url}: status {status}", file=sys.stderr)
        return None
    return text

def main():
    index_url = 'https://en.tass.ru/sitemap.xml'
    index_xml = fetch_sitemap(index_url)
    if not index_xml:
        sys.exit(1)
    root = ET.fromstring(index_xml)
    # Determine namespace from root tag (could be 0.9 or 0.91)
    ns_uri = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
    ns = {'s': ns_uri}
    sitemap_urls = []
    for sm in root.findall('s:sitemap', ns):
        loc_el = sm.find('s:loc', ns)
        if loc_el is not None and loc_el.text:
            sitemap_urls.append(loc_el.text.strip())
    # also include the hot sitemap directly (may not be listed)
    if 'https://tass.com/sitemap/sitemap_hot.xml' not in sitemap_urls:
        sitemap_urls.append('https://tass.com/sitemap/sitemap_hot.xml')

    urls_by_date = {}
    all_urls = {}
    for sm_url in sitemap_urls:
        txt = fetch_sitemap(sm_url)
        if not txt:
            continue
        try:
            sm_root = ET.fromstring(txt)
        except ET.ParseError as e:
            print(f"Parse error in {sm_url}: {e}", file=sys.stderr)
            continue
        for url_el in sm_root.findall('.//{*}url'):
            loc = url_el.find('{*}loc')
            lm = url_el.find('{*}lastmod')
            if loc is None or lm is None:
                continue
            url = loc.text.strip()
            date = parse_date(lm.text.strip())
            if date is None:
                continue
            if START <= date <= END:
                # dedupe
                if url in all_urls:
                    continue
                all_urls[url] = date
                urls_by_date.setdefault(date, []).append(url)
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'tass-ru.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(all_urls.items(), key=lambda x: x[1]):
            f.write(f"{url}\t{date.isoformat()}\n")
    # Print per‑day counts
    for day in (START + datetime.timedelta(days=i) for i in range((END-START).days + 1)):
        count = len(urls_by_date.get(day, []))
        if count:
            print(f"{day.isoformat()}: {count} URLs")

if __name__ == '__main__':
    main()
