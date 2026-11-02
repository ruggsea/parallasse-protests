#!/usr/bin/env python3
import os, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://www.tvonenews.com'
SITEMAP_INDEX = f'{BASE_URL}/sitemap.xml'
START = datetime.strptime('2026-09-25', '%Y-%m-%d').date()
END = datetime.strptime('2026-10-25', '%Y-%m-%d').date()

def parse_sitemap(xml_text):
    """Yield (url, date) tuples from a sitemap XML string.
    Supports standard <url> entries with optional <news:publication_date>.
    """
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    root = ET.fromstring(xml_text.encode('utf-8'))
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # try news:publication_date first
        pubdate_el = url_el.find('.//news:publication_date', ns)
        if pubdate_el is not None and pubdate_el.text:
            # format like 2026-10-26T01:09:38+07:00
            try:
                dt = datetime.fromisoformat(pubdate_el.text.strip())
                date = dt.date()
            except Exception:
                date = None
        else:
            # fallback to <lastmod>
            lastmod_el = url_el.find('ns:lastmod', ns)
            if lastmod_el is not None and lastmod_el.text:
                try:
                    dt = datetime.fromisoformat(lastmod_el.text.strip())
                    date = dt.date()
                except Exception:
                    date = None
            else:
                date = None
        if date is None:
            continue
        yield url, date

def fetch_and_collect():
    # first fetch sitemap index
    status, text, _ = fetch(SITEMAP_INDEX)
    if status != 200:
        raise RuntimeError(f'Failed to fetch sitemap index: {status}')
    # parse index to get all sitemap URLs
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(text.encode('utf-8'))
    sitemap_urls = []
    for sm in root.findall('ns:sitemap', ns):
        loc = sm.find('ns:loc', ns)
        if loc is not None:
            sitemap_urls.append(loc.text.strip())
    # also include the news-sitemap directly if not listed (some sites separate)
    if f'{BASE_URL}/sitemap/news/news-sitemap.xml' not in sitemap_urls:
        sitemap_urls.append(f'{BASE_URL}/sitemap/news/news-sitemap.xml')
    results = {}
    for sm_url in sitemap_urls:
        status, sm_text, _ = fetch(sm_url)
        if status != 200:
            continue
        for url, date in parse_sitemap(sm_text):
            if START <= date <= END:
                results[url] = date
    return results

def main():
    urls_dates = fetch_and_collect()
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'tvonenews-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(urls_dates.items(), key=lambda x: x[1]):
            f.write(f"{url}\t{date.isoformat()}\n")
    # print per‑day counts
    from collections import Counter
    cnt = Counter(date.isoformat() for date in urls_dates.values())
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")
    print('Total URLs written:', len(urls_dates))

if __name__ == '__main__':
    main()
