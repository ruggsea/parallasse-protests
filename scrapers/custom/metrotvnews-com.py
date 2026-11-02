#!/usr/bin/env python3
"""Scrape MetroTVNews article URLs for a date range.

Outputs a TSV file at data/urls_custom/metrotvnews-com.tsv with columns:
    URL<TAB>YYYY-MM-DD
One line per unique article URL, date taken from the sitemap's
news:publication_date (or <lastmod> fallback). The script prints a summary
of how many URLs were written per day.
"""
import os
import sys
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure the polite_fetch module is on the path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(BASE_DIR, 'scrapers'))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)
# Wayback fallback helper – fetch CDX JSON and return list of (url, date)
def fetch_wayback_cdx(domain, start, end):
    # start/end in YYYYMMDD format
    url = (
        f"https://web.archive.org/cdx/search/cdx?url={domain}/*&from={start}&to={end}"
        "&output=json&collapse=urlkey"
    )
    try:
        status, text, _ = fetch(url)
    except Exception:
        return []
    if status != 200:
        return []
    import json
    try:
        data = json.loads(text)
    except Exception:
        return []
    # first row is header
    if not data or len(data) < 2:
        return []
    header = data[0]
    # Find index of original URL and timestamp
    try:
        idx_original = header.index('original')
        idx_timestamp = header.index('timestamp')
    except ValueError:
        return []
    results = []
    for row in data[1:]:
        try:
            original = row[idx_original]
            ts = row[idx_timestamp]
            # timestamp format YYYYMMDDhhmmss
            dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
            results.append((original, dt.date()))
        except Exception:
            continue
    return results

START_DATE = datetime.date(2026, 9, 25)
END_DATE   = datetime.date(2026, 10, 25)  # inclusive

SITEMAP_INDEX = 'https://www.metrotvnews.com/sitemap/sitemap.xml'

NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9',
}

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: status {status}')
    return text

def parse_sitemap_index(text):
    root = ET.fromstring(text)
    locs = []
    for sm in root.findall('sm:sitemap', NS):
        loc = sm.find('sm:loc', NS)
        if loc is not None and loc.text:
            locs.append(loc.text.strip())
    return locs

def parse_sitemap(text):
    root = ET.fromstring(text)
    entries = []
    for url_el in root.findall('sm:url', NS):
        loc_el = url_el.find('sm:loc', NS)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date first
        date_el = url_el.find('news:news/news:publication_date', NS)
        if date_el is None or not date_el.text:
            # Fallback to <lastmod>
            date_el = url_el.find('sm:lastmod', NS)
        if date_el is None or not date_el.text:
            continue
        date_str = date_el.text.strip()
        # Extract date part (YYYY-MM-DD) ignoring time zone
        try:
            dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            # fallback split
            dt = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d')
        date = dt.date()
        entries.append((url, date))
    return entries

def main():
    try:
        index_text = fetch_text(SITEMAP_INDEX)
    except Exception as e:
        sys.stderr.write(f'Error fetching sitemap index: {e}\n')
        sys.exit(1)
    sitemap_urls = parse_sitemap_index(index_text)
    # Collect URLs within range
    url_date_map = {}
    for sm_url in sitemap_urls:
        try:
            sm_text = fetch_text(sm_url)
        except Exception as e:
            sys.stderr.write(f'Warning: could not fetch {sm_url}: {e}\n')
            continue
        for url, pub_date in parse_sitemap(sm_text):
            if START_DATE <= pub_date <= END_DATE:
                if url not in url_date_map:
                    url_date_map[url] = pub_date
    # If some days are sparse, supplement with Wayback CDX
    # Determine missing dates in the range
    needed_dates = set(START_DATE + datetime.timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1))
    present_dates = set(url_date_map.values())
    missing_dates = needed_dates - present_dates
    if missing_dates:
        # Fetch CDX for whole range (might include extra dates)
        cdx_results = fetch_wayback_cdx('metrotvnews.com', START_DATE.strftime('%Y%m%d'), END_DATE.strftime('%Y%m%d'))
        for orig_url, dt in cdx_results:
            if not (START_DATE <= dt <= END_DATE):
                continue
            if orig_url in url_date_map:
                continue
            # Prefer URLs that look like article pages (contain '/read/')
            if '/read/' in orig_url:
                url_date_map[orig_url] = dt
    # Archive fallback: iterate each day and pull article links
    for single_date in (START_DATE + datetime.timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)):
        archive_url = f"https://www.metrotvnews.com/archivio/{single_date.year}/{single_date.month}/{single_date.day}"
        try:
            page_text = fetch_text(archive_url)
        except Exception:
            continue
        # extract article links
        import re
        links = set(re.findall(r"/read/[^\"'\s>]+", page_text))
        for rel in links:
            full_url = f"https://www.metrotvnews.com{rel}"
            # Prefer archive date over any earlier source
            if full_url not in url_date_map:
                url_date_map[full_url] = single_date
    # Write TSV
    out_path = os.path.abspath(os.path.join(BASE_DIR, 'data', 'urls_custom', 'metrotvnews-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sorted_items = sorted(url_date_map.items(), key=lambda kv: (kv[1], kv[0]))
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted_items:
            f.write(f"{url}\t{d.isoformat()}\n")
    # Print per‑day counts
    counts = defaultdict(int)
    for d in url_date_map.values():
        counts[d] += 1
    for d in sorted(counts):
        print(f"{d.isoformat()}: {counts[d]} URLs")
    print(f"Wrote {len(sorted_items)} unique URLs to {out_path}")

if __name__ == '__main__':
    main()
