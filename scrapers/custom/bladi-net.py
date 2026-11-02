#!/usr/bin/env python3

import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Ensure the polite_fetch module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch not found. Ensure it is installed in the project.\n')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX = 'https://www.bladi.net/sitemap.xml'

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch {url}: status {status}\n')
        return None
    return text

def parse_sitemap(url):
    txt = fetch_text(url)
    if not txt:
        return []
    try:
        root = ET.fromstring(txt)
    except ET.ParseError as e:
        sys.stderr.write(f'XML parse error for {url}: {e}\n')
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod = lastmod_el.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
        except ValueError:
            continue
        date = dt.date()
        if START <= date <= END:
            entries.append((loc, date.isoformat()))
    return entries

def main():
    # fetch sitemap index
    index_txt = fetch_text(SITEMAP_INDEX)
    if not index_txt:
        sys.exit(1)
    try:
        root = ET.fromstring(index_txt)
    except ET.ParseError as e:
        sys.stderr.write(f'Failed to parse sitemap index: {e}\n')
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [loc.text.strip() for loc in root.findall('.//ns:loc', ns)]

    results = {}
    # First, try the XML sitemaps (they contain recent <lastmod> dates)
    for sm_url in sitemap_urls:
        entries = parse_sitemap(sm_url)
        for url, date in entries:
            results[url] = date  # deduplicate

    # Fallback: use Wayback CDX for the whole window if needed (or to supplement)
    # CDX returns rows: ["urlkey","timestamp","original",...]
    cdx_url = (
        "http://web.archive.org/cdx/search/cdx?url=bladi.net/*"
        f"&from={START.strftime('%Y%m%d')}&to={END.strftime('%Y%m%d')}"
        "&output=json&collapse=urlkey"
    )
    cdx_text = fetch_text(cdx_url)
    if cdx_text:
        import json
        try:
            rows = json.loads(cdx_text)
            header = rows[0]
            for row in rows[1:]:
                # row indices: 0 urlkey, 1 timestamp, 2 original, 3 mimetype, 4 statuscode, ...
                orig = row[2]
                ts = row[1]
                if not orig.lower().endswith('.html'):
                    continue
                try:
                    dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
                except ValueError:
                    continue
                date_str = dt.date().isoformat()
                if START <= dt.date() <= END:
                    results.setdefault(orig, date_str)
        except Exception as e:
            sys.stderr.write(f'Error parsing CDX JSON: {e}\n')

    # Output file
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'bladi-net.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # sort by date then url
    sorted_items = sorted(results.items(), key=lambda x: (x[1], x[0]))
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted_items:
            f.write(f"{url}\t{date}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(date for _, date in sorted_items)
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
