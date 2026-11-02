#!/usr/bin/env python3

import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure the project root is in sys.path for polite_fetch
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scrapers'))

from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

BASE_URL = 'https://gestion.pe'
SITEMAP_INDEX = f'{BASE_URL}/sitemap/?outputType=xml'

def parse_date(date_str: str) -> datetime.date:
    # Handles ISO datetime with timezone, e.g., 2026-10-26T01:00:00-05:00
    try:
        dt = datetime.datetime.fromisoformat(date_str)
        return dt.date()
    except ValueError:
        # fallback: just first 10 chars
        return datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').date()

def fetch_xml(url: str) -> ET.Element:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: HTTP {status}')
    return ET.fromstring(text)

def collect_urls() -> dict:
    """Return dict mapping URL -> publication date (datetime.date).
    Includes a fallback to Wayback CDX for dates lacking enough URLs.
    """
    results = {}
    # First fetch the index sitemap
    root = fetch_xml(SITEMAP_INDEX)
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for sitemap in root.findall('s:sitemap', ns):
        loc_el = sitemap.find('s:loc', ns)
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        try:
            cat_root = fetch_xml(loc)
        except Exception:
            continue
        if cat_root.tag.endswith('sitemapindex'):
            for sub in cat_root.findall('s:sitemap', ns):
                sub_loc = sub.find('s:loc', ns)
                if sub_loc is not None:
                    process_urlset(sub_loc.text.strip(), results)
        else:
            process_urlset(loc, results)

    # Ensure each target date has at least 15 URLs; fallback to Wayback CDX if needed
    from collections import defaultdict
    date_counts = defaultdict(int)
    for d in results.values():
        date_counts[d] += 1
    needed_dates = [d for d in (START_DATE + datetime.timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)) if date_counts[d] < 15]
    for missing in needed_dates:
        # Wayback CDX query for that single day
        ymd = missing.strftime('%Y%m%d')
        cdx_url = f'https://web.archive.org/cdx/search/cdx?url=gestion.pe/*&from={ymd}&to={ymd}&output=json&fl=original,timestamp'
        try:
            status, txt, _ = fetch(cdx_url)
        except Exception:
            continue
        if status != 200:
            continue
        try:
            import json as _json
            rows = _json.loads(txt)
        except Exception:
            continue
        # rows[0] is header ['original','timestamp']
        for row in rows[1:]:
            url, ts = row
            # ts format YYYYMMDDhhmmss
            url_date = datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
            if url_date == missing and url not in results:
                results[url] = missing
                date_counts[missing] += 1
                if date_counts[missing] >= 15:
                    break
        # end for rows
    return results

def process_urlset(urlset_url: str, results: dict):
    try:
        root = fetch_xml(urlset_url)
    except Exception:
        return
    ns = {
        's': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    for url_el in root.findall('s:url', ns):
        loc_el = url_el.find('s:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date first
        pub_date = None
        news_el = url_el.find('news:news', ns)
        if news_el is not None:
            pub_el = news_el.find('news:publication_date', ns)
            if pub_el is not None and pub_el.text:
                pub_date = parse_date(pub_el.text.strip())
        if pub_date is None:
            # fallback to lastmod
            lastmod_el = url_el.find('s:lastmod', ns)
            if lastmod_el is not None and lastmod_el.text:
                pub_date = parse_date(lastmod_el.text.strip())
        if pub_date is None:
            continue
        if START_DATE <= pub_date <= END_DATE:
            results[url] = pub_date

def write_tsv(url_date_map: dict):
    out_path = os.path.join(PROJECT_ROOT, 'data', 'urls_custom', 'gestion-pe.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(url_date_map.items()):
            f.write(f"{url}\t{d.isoformat()}\n")
    print(f'Wrote {len(url_date_map)} URLs to {out_path}')

def main():
    url_date_map = collect_urls()
    write_tsv(url_date_map)
    # Simple per‑day count output
    counts = {}
    for d in url_date_map.values():
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f'{d}: {counts[d]}')

if __name__ == '__main__':
    main()
