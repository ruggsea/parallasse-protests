#!/usr/bin/env python3
import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END   = datetime.date(2026, 10, 25)

SITEMAP_URL = 'https://www.reforma.com/sitemap_all.xml'

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch sitemap {url}: status {status}')
    return text

def parse_dates(xml_text):
    # Parse XML, yielding (url, date)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    # ElementTree can handle default namespace without prefix by using it in tag
    root = ET.fromstring(xml_text)
    for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        lastmod_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        # Only keep article URLs ending with /ar<number>
        if not url.rsplit('/', 1)[-1].startswith('ar'):
            continue
        # Parse lastmod ISO format, may include timezone or fractional seconds
        dt_str = lastmod_el.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            # fallback: split at T
            dt = datetime.datetime.strptime(dt_str.split('T')[0], '%Y-%m-%d')
        yield url, dt.date()

def main():
    xml = fetch_sitemap(SITEMAP_URL)
    records = []
    for url, pub_date in parse_dates(xml):
        if START <= pub_date <= END:
            records.append((url, pub_date))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for url, d in records:
        if url not in seen:
            seen.add(url)
            unique.append((url, d))
    # Write TSV
    out_path = os.path.join('data', 'urls_custom', 'reforma-com.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in unique:
            f.write(f"{url}\t{d.isoformat()}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(d.isoformat() for _, d in unique)
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")
    print(f"Wrote {len(unique)} URLs to {out_path}")

if __name__ == '__main__':
    main()
