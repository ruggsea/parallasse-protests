#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = 'https://www.efsyn.gr'
SITEMAP_INDEX = f'{BASE}/sitemap_index.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def iso_to_date(s):
    try:
        return datetime.datetime.fromisoformat(s).date()
    except Exception:
        return None

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {url} status {status}', file=sys.stderr)
        return None
    return ET.fromstring(text)

def main():
    index_root = fetch_xml(SITEMAP_INDEX)
    if index_root is None:
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls_by_day = defaultdict(list)
    seen = set()
    # find all post-sitemap entries
    for sm in index_root.findall('ns:sitemap', ns):
        loc = sm.find('ns:loc', ns).text
        if not loc.lower().endswith('.xml'):
            continue
        if 'post-sitemap' not in loc:
            continue
        try:
            root = fetch_xml(loc)
        except Exception as e:
            print(f'Parse error for {loc}: {e}', file=sys.stderr)
            continue
        if root is None:
            continue
        for url_el in root.findall('ns:url', ns):
            loc_el = url_el.find('ns:loc', ns)
            lm_el = url_el.find('ns:lastmod', ns)
            if loc_el is None:
                continue
            url = loc_el.text.strip()
            if url in seen:
                continue
            seen.add(url)
            if lm_el is None:
                continue
            lm_date = iso_to_date(lm_el.text.strip())
            if lm_date is None:
                continue
            if START <= lm_date <= END:
                urls_by_day[lm_date].append(url)
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'efsyn-gr.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for day in sorted(urls_by_day):
            for u in urls_by_day[day]:
                f.write(f"{u}\t{day.isoformat()}\n")
    # print per‑day counts
    for day in sorted(urls_by_day):
        print(f"{day}: {len(urls_by_day[day])} URLs")

if __name__ == '__main__':
    main()
