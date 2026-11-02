#!/usr/bin/env python3
"""Scrape article URLs from eltrecetv.com.ar between 2026-09-25 and 2026-10-25.
Uses the site's sitemap (allowed by robots.txt) via polite_fetch.
Writes TSV with URL and publication date (YYYY-MM-DD) to data/urls_custom/eltrecetv-com-ar.tsv.
Prints per‑day counts.
"""
import os, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from polite_fetch import fetch

# Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))  # project root
OUT_TSV = os.path.join(BASE_DIR, 'data', 'urls_custom', 'eltrecetv-com-ar.tsv')
SITEMAP_URL = 'https://www.eltrecetv.com.ar/arc/outboundfeeds/news-sitemap/?outputType=xml'
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def date_from_url(url: str):
    """Extract date from URL pattern /YYYY/MM/DD/ returning a datetime or None."""
    m = re.search(r'/((\d{4})/(\d{2})/(\d{2}))/', url)
    if not m:
        return None
    try:
        # m.group(1) is like '2026/10/25'
        return datetime.strptime(m.group(1), '%Y/%m/%d')
    except ValueError:
        return None

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap: HTTP {status}', file=sys.stderr)
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Prefer date from URL; fallback to lastmod if present
        pub_date = date_from_url(url)
        if pub_date is None and lastmod_el is not None:
            try:
                pub_date = datetime.fromisoformat(lastmod_el.text.strip().split('T')[0])
            except Exception:
                continue
        if pub_date is None:
            continue
        if START <= pub_date <= END:
            yield url, pub_date.date().isoformat()

def main():
    # First try the news sitemap (recent articles)
    xml = fetch_sitemap(SITEMAP_URL)
    # Collect URLs from sitemap
    seen = set()
    per_day = {}
    for url, date_str in parse_sitemap(xml):
        if url in seen:
            continue
        seen.add(url)
        per_day.setdefault(date_str, []).append(url)
    # Fallback: Wayback CDX for missing dates
    needed_dates = []
    cur = START
    while cur <= END:
        ds = cur.date().isoformat()
        if ds not in per_day:
            needed_dates.append(ds)
        cur += timedelta(days=1)
    if needed_dates:
        import time
        for ds in needed_dates:
            # Use Wayback CDX to get URLs for this day
            from_date = ds.replace('-','')
            to_date = ds.replace('-','')
            cdx_url = f'http://web.archive.org/cdx/search/cdx?url=www.eltrecetv.com.ar/*&from={from_date}&to={to_date}&output=json&collapse=urlkey'
            for attempt in range(3):
                status, txt, _ = fetch(cdx_url)
                if status == 200:
                    break
                time.sleep(2**attempt)
            if status != 200:
                continue
            import json
            try:
                data = json.loads(txt)
            except Exception:
                continue
            for row in data[1:]:  # first row is header
                url = row[2]
                if not url.startswith('http'):
                    url = 'https://www.eltrecetv.com.ar' + url
                # dedupe and add
                if url in seen:
                    continue
                seen.add(url)
                per_day.setdefault(ds, []).append(url)
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    # Write TSV sorted by date then URL
    with open(OUT_TSV, 'w', encoding='utf-8') as out:
        for date in sorted(per_day):
            for u in sorted(per_day[date]):
                out.write(f"{u}\t{date}\n")
    # Print counts
    for date in sorted(per_day):
        print(f"{date}: {len(per_day[date])} URLs")
    total = sum(len(v) for v in per_day.values())
    print(f"Total URLs: {total}")

    # Collect unique URLs
    seen = set()
    per_day = {}
    for url, date_str in parse_sitemap(xml):
        if url in seen:
            continue
        seen.add(url)
        per_day.setdefault(date_str, []).append(url)
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    # Write TSV sorted by date then URL
    with open(OUT_TSV, 'w', encoding='utf-8') as out:
        for date in sorted(per_day):
            for u in sorted(per_day[date]):
                out.write(f"{u}\t{date}\n")
    # Print counts
    for date in sorted(per_day):
        print(f"{date}: {len(per_day[date])} URLs")
    total = sum(len(v) for v in per_day.values())
    print(f"Total URLs: {total}")

if __name__ == '__main__':
    main()
