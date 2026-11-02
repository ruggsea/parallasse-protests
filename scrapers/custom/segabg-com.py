#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://www.segabg.com'
SITEMAP_INDEX = f'{BASE_URL}/sitemap.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {url} -> {status}', file=sys.stderr)
        return None
    return ET.fromstring(text)

def parse_sitemap(sitemap_url):
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        lastmod = url.find('ns:lastmod', ns)
        if loc is None:
            continue
        u = loc.text.strip()
        d = None
        if lastmod is not None and lastmod.text:
            # parse date part only
            try:
                d = datetime.datetime.fromisoformat(lastmod.text.strip()).date()
            except Exception:
                # fallback to first 10 chars
                d = datetime.date.fromisoformat(lastmod.text.strip()[:10])
        entries.append((u, d))
    return entries

def main():
    # fetch index
    index_root = fetch_xml(SITEMAP_INDEX)
    if index_root is None:
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = []
    for sm in index_root.findall('ns:sitemap', ns):
        loc = sm.find('ns:loc', ns)
        if loc is not None:
            sitemap_urls.append(loc.text.strip())
    # collect entries
    collected = []
    for sm_url in sitemap_urls:
        entries = parse_sitemap(sm_url)
        for u, d in entries:
            if d is None:
                continue
            if START <= d <= END:
                collected.append((u, d))
    # deduplicate preserving earliest date (should be same)
    uniq = {}
    for u, d in collected:
        if u not in uniq:
            uniq[u] = d
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'segabg-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in sorted(uniq.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{u}\t{d.isoformat()}\n")
    # print per‑day counts
    counts = defaultdict(int)
    for d in uniq.values():
        counts[d] += 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")

if __name__ == '__main__':
    main()
