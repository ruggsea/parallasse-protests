#!/usr/bin/env python3

import sys
import os
import json
import datetime
import xml.etree.ElementTree as ET

# Add scrapers directory to path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX = 'https://cdn.falter.at/sitemap.xml'

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: status {status}', file=sys.stderr)
        return None
    return text

def parse_sitemap(url, out_dict):
    txt = fetch_text(url)
    if not txt:
        return
    try:
        root = ET.fromstring(txt)
    except ET.ParseError as e:
        print(f'XML parse error for {url}: {e}', file=sys.stderr)
        return
    # Namespace handling (default sitemap namespace)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None:
            continue
        url_val = loc.text.strip()
        if lastmod is None or not lastmod.text:
            continue
        # extract date part
        # Prefer date from URL path if present (YYYYMMDD), else fallback to <lastmod>
        import re
        # Try to extract date from URL in various formats
        d = None
        # Format YYYYMMDD contiguous
        m = re.search(r"(\d{8})", url_val)
        if m:
            try:
                d = datetime.datetime.strptime(m.group(1), '%Y%m%d').date()
            except ValueError:
                d = None
        # If not found, try YYYY/MM/DD or YYYY-MM-DD
        if d is None:
            m2 = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", url_val)
            if m2:
                try:
                    d = datetime.datetime.strptime(f"{m2.group(1)}{m2.group(2)}{m2.group(3)}", '%Y%m%d').date()
                except ValueError:
                    d = None
        # If still no date or out of range, fall back to <lastmod>
        if d is None or not (START <= d <= END):
            date_str = lastmod.text.strip()[:10]
            try:
                d = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                d = None
        if d and START <= d <= END:
            out_dict[url_val] = d.isoformat()

def main():
    # fetch sitemap index
    index_txt = fetch_text(SITEMAP_INDEX)
    if not index_txt:
        sys.exit(1)
    try:
        index_root = ET.fromstring(index_txt)
    except ET.ParseError as e:
        print(f'Failed to parse sitemap index: {e}', file=sys.stderr)
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = []
    for sm in index_root.findall('.//ns:sitemap/ns:loc', ns):
        loc = sm.text.strip()
        # include all sitemaps
        sitemap_urls.append(loc)
    results = {}
    for sm_url in sitemap_urls:
        parse_sitemap(sm_url, results)
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'falter-at.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # sort by date then url
    items = sorted(results.items(), key=lambda x: (x[1], x[0]))
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in items:
            f.write(f"{url}\t{date}\n")
    # per-day counts
    counts = {}
    for _, date in items:
        counts[date] = counts.get(date, 0) + 1
    for date in sorted(counts):
        print(f"{date}\t{counts[date]}")

if __name__ == '__main__':
    main()
