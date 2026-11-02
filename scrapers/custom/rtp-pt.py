#!/usr/bin/env python3
import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://www.rtp.pt/noticias/sitemap"

def parse_iso(date_str):
    # Handles formats like 2026-10-26T06:32:26+00:00
    try:
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        # fallback split
        dt = datetime.datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
    return dt.date()

def main():
    status, text, _ = fetch(SITEMAP_URL)
    if status != 200:
        print(f"Failed to fetch sitemap: status {status}")
        sys.exit(1)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
        sys.exit(1)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    # The default namespace is the sitemap namespace; ElementTree requires full tag
    # We'll ignore namespaces by looking for tags ending with 'url', 'loc', etc.
    urls_by_date = {}
    for url_el in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date first
        pub_date_el = url_el.find('.//{http://www.google.com/schemas/sitemap-news/0.9}publication_date')
        if pub_date_el is not None and pub_date_el.text:
            pub_date = parse_iso(pub_date_el.text.strip())
        else:
            lastmod_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            if lastmod_el is None or not lastmod_el.text:
                continue
            pub_date = parse_iso(lastmod_el.text.strip())
        if START_DATE <= pub_date <= END_DATE:
            urls_by_date.setdefault(pub_date, set()).add(url)
    # Write output
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'rtp-pt.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for d in sorted(urls_by_date):
            for u in sorted(urls_by_date[d]):
                f.write(f"{u}\t{d.isoformat()}\n")
                total += 1
    # Print per-day counts
    for d in sorted(urls_by_date):
        print(f"{d}: {len(urls_by_date[d])} URLs")
    print(f"Total URLs written: {total}")

if __name__ == "__main__":
    main()
