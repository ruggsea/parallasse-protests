#!/usr/bin/env python3
import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://bnrnews.bg/api/program-sitemap/main"

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}, status {status}")
    return text

def parse_sitemap(xml_text):
    # Parse XML, handling namespace
    root = ET.fromstring(xml_text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        lastmod = lastmod_el.text.strip()
        yield url, lastmod

def main():
    xml = fetch_sitemap(SITEMAP_URL)
    records = []
    for url, lastmod in parse_sitemap(xml):
        try:
            d = datetime.datetime.strptime(lastmod, "%Y-%m-%d").date()
        except ValueError:
            continue
        if START <= d <= END:
            records.append((url, d.isoformat()))
    # Deduplicate
    uniq = {}
    for u, d in records:
        uniq[u] = d
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'bnr-bg.tsv') )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in sorted(uniq.items()):
            f.write(f"{u}\t{d}\n")
    # Print per-day counts
    from collections import Counter
    cnt = Counter(d for _, d in uniq.items())
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == "__main__":
    main()
