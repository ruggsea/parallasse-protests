#!/usr/bin/env python3
import sys, os, xml.etree.ElementTree as ET, datetime, re

# Ensure the polite_fetch module path is available (relative to repo root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

SITEMAP_URL = 'https://www.internazionale.it/sitemaps/sitemap_news.xml'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'internazionale-it.tsv'))

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date(date_str: str) -> datetime.date:
    # date may be like 2026-09-30T12:34:56+02:00
    # strip timezone and time part
    m = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
    if not m:
        raise ValueError(f'Unexpected date format: {date_str}')
    return datetime.datetime.strptime(m.group(1), '%Y-%m-%d').date()

def main():
    status, text, _ = fetch(SITEMAP_URL)
    if status != 200:
        print(f'Failed to fetch sitemap: HTTP {status}', file=sys.stderr)
        sys.exit(1)
    # Parse XML (may contain namespaces)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1',
    }
    root = ET.fromstring(text)
    urls = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        date_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or date_el is None:
            continue
        url = loc_el.text.strip()
        pub_date = parse_date(date_el.text.strip())
        if START <= pub_date <= END:
            urls.append((url, pub_date.isoformat()))
    # Deduplicate
    seen = set()
    unique = []
    for u, d in urls:
        if u not in seen:
            seen.add(u)
            unique.append((u, d))
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for u, d in unique:
            f.write(f"{u}\t{d}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(d for _, d in unique)
    for day in sorted(cnt):
        print(f"{day}: {cnt[day]} URLs")

if __name__ == '__main__':
    main()
