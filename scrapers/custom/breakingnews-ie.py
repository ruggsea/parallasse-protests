#!/usr/bin/env python3

import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure the polite_fetch library is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise RuntimeError('polite_fetch module not found')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_sitemap(month: str, page: int):
    url = f"https://www.breakingnews.ie/sitemap/posts/{month}/page/{page}"
    status, text, _ = fetch(url)
    return status, text

def parse_sitemap(xml_text: str):
    # Parse XML, return list of (url, date)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        lastmod = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        # lastmod like 2026-09-01T16:57:58+01:00
        try:
            dt = datetime.datetime.fromisoformat(lastmod.text.strip())
        except Exception:
            continue
        date = dt.date()
        entries.append((url, date))
    return entries

def main():
    months = ['202609', '202610']
    collected = {}
    for month in months:
        page = 1
        while True:
            status, text = fetch_sitemap(month, page)
            if status != 200:
                break
            try:
                entries = parse_sitemap(text)
            except Exception as e:
                # malformed XML, stop this month
                break
            if not entries:
                break
            for url, date in entries:
                if START <= date <= END:
                    collected[url] = date.isoformat()
            page += 1
    # Write TSV
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom')
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'breakingnews-ie.tsv')
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date_str in sorted(collected.items()):
            f.write(f"{url}\t{date_str}\n")
    # Print per‑day counts
    counts = {}
    for d in collected.values():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")
    print(f"Total URLs written: {len(collected)}")

if __name__ == '__main__':
    main()
