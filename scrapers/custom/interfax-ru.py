#!/usr/bin/env python3
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Add the scraper helpers path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

SITEMAP_URL = "https://www.interfax.ru/SEO_SiteMapLastChanges.xml"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'interfax-ru.tsv')
)

START = datetime.strptime('2026-09-25', '%Y-%m-%d').date()
END = datetime.strptime('2026-10-25', '%Y-%m-%d').date()

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap: {url} status {status}")
    return text

def parse_sitemap(xml_text):
    root = ET.fromstring(xml_text)
    # Namespace handling (if any). The sitemap likely has no namespace for urlset.
    entries = []
    for url in root.findall('.//url'):
        loc_el = url.find('loc')
        lastmod_el = url.find('lastmod')
        if loc_el is None or lastmod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod_raw = lastmod_el.text.strip()
        # Parse ISO datetime with optional timezone
        try:
            dt = datetime.fromisoformat(lastmod_raw.replace('Z', '+00:00'))
        except Exception:
            # fallback: split at T
            dt = datetime.strptime(lastmod_raw.split('T')[0], '%Y-%m-%d')
        date = dt.date()
        entries.append((loc, date))
    return entries

def filter_entries(entries, start, end):
    return [(url, d.isoformat()) for url, d in entries if start <= d <= end]

def write_tsv(pairs, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    uniq = {}
    for url, date in pairs:
        uniq[url] = date  # last occurrence wins but dates should be same
    with open(path, 'w', encoding='utf-8') as f:
        for url, date in uniq.items():
            f.write(f"{url}\t{date}\n")

def main():
    xml = fetch_sitemap(SITEMAP_URL)
    entries = parse_sitemap(xml)
    filtered = filter_entries(entries, START, END)
    write_tsv(filtered, OUTPUT_TSV)
    # Simple report per day
    from collections import Counter
    cnt = Counter(date for _, date in filtered)
    for day in sorted(cnt):
        print(f"{day}: {cnt[day]} URLs")

if __name__ == "__main__":
    main()
