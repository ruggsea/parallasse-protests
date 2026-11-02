#!/usr/bin/env python3
"""Scrape Ethnos (ethnos.gr) article URLs for a date range.
Outputs TSV at data/urls_custom/ethnos-gr.tsv with columns:
URL<TAB>YYYY-MM-DD (publication date from sitemap lastmod).
Uses polite_fetch fetch to respect robots.txt.
"""
import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure the repo's scraper helpers are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch not found\n')
    sys.exit(1)

BASE_URL = 'https://www.ethnos.gr'
SITEMAP_URLS = [
    f'{BASE_URL}/articles-sitemap',
    f'{BASE_URL}/googleSitemap',
]
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'ethnos-gr.tsv'))

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch {url}: HTTP {status}\n')
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    # Returns list of (url, date) where date is datetime.date
    root = ET.fromstring(xml_text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    news_ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url_elem in root.findall('ns:url', ns):
        loc_elem = url_elem.find('ns:loc', ns)
        if loc_elem is None:
            continue
        url = loc_elem.text.strip()
        # Try <lastmod>
        date = None
        lastmod_elem = url_elem.find('ns:lastmod', ns)
        if lastmod_elem is not None and lastmod_elem.text:
            dt_str = lastmod_elem.text.strip()
            try:
                dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                date = dt.date()
            except Exception:
                try:
                    date = datetime.datetime.strptime(dt_str[:10], '%Y-%m-%d').date()
                except Exception:
                    date = None
        # Try news:publication_date if date still None
        if date is None:
            pub_elem = url_elem.find('news:news/news:publication_date', {**ns, **news_ns})
            if pub_elem is not None and pub_elem.text:
                # Format: DD-MM-YYYYTHH:MM+TZ
                dt_str = pub_elem.text.strip()
                # Remove timezone part after +' or 'Z'
                if '+' in dt_str:
                    dt_str = dt_str.split('+')[0]
                elif '-' in dt_str[10:]:  # timezone after time
                    dt_str = dt_str[:10]
                # Expected format DD-MM-YYYYTHH:MM
                try:
                    dt = datetime.datetime.strptime(dt_str[:10], '%d-%m-%Y')
                    date = dt.date()
                except Exception:
                    date = None
        if date is None:
            continue
        entries.append((url, date))
    return entries

def filter_entries(entries):
    filtered = []
    for url, date in entries:
        if START_DATE <= date <= END_DATE:
            filtered.append((url, date))
    return filtered

def dedupe(entries):
    seen = set()
    uniq = []
    for url, date in entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, date))
    return uniq

def write_tsv(entries):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in entries:
            f.write(f"{url}\t{date.isoformat()}\n")

def fetch_wayback():
    wayback_url = (
        'http://web.archive.org/cdx/search/cdx?url=www.ethnos.gr/*'
        '&from=20260925&to=20261025&output=json&collapse=urlkey'
    )
    status, text, _ = fetch(wayback_url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch Wayback CDX: HTTP {status}\n')
        return []
    import json
    try:
        data = json.loads(text)
    except Exception as e:
        sys.stderr.write(f'Failed to parse Wayback JSON: {e}\n')
        return []
    entries = []
    # First row is header
    for row in data[1:]:
        # row format: [urlkey, timestamp, original, mime, statuscode, digest, length]
        if len(row) < 3:
            continue
        original_url = row[2]
        timestamp = row[1]
        try:
            dt = datetime.datetime.strptime(timestamp[:8], '%Y%m%d')
            date = dt.date()
        except Exception:
            continue
        entries.append((original_url, date))
    return entries


def main():
    all_entries = []
    for sitemap_url in SITEMAP_URLS:
        xml = fetch_sitemap(sitemap_url)
        all_entries.extend(parse_sitemap(xml))
    # Include Wayback entries as fallback/augmentation
    all_entries.extend(fetch_wayback())
    filtered = filter_entries(all_entries)
    uniq = dedupe(filtered)
    uniq.sort(key=lambda x: (x[1], x[0]))
    write_tsv(uniq)
    counts = defaultdict(int)
    for _, d in uniq:
        counts[d] += 1
    for d in sorted(counts):
        print(f"{d}: {counts[d]} URLs")
    print(f"Total {len(uniq)} URLs written to {OUTPUT_TSV}")

if __name__ == '__main__':
    main()
