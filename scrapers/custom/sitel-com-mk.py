#!/usr/bin/env python3
"""Scrape article URLs from Sitel (sitel.com.mk) for dates 2026-09-25 to 2026-10-25.
Outputs TSV at data/urls_custom/sitel-com-mk.tsv with columns: URL<TAB>YYYY-MM-DD.
Uses polite_fetch.fetch for all HTTP requests.
"""
import sys
import os
import csv
import datetime
import time
import xml.etree.ElementTree as ET

# Add the scrapers directory to sys.path for polite_fetch import
scrapers_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, scrapers_dir)
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_rss():
    """Fetch the RSS feed and return list of (url, date) within range."""
    status, text, _ = fetch('https://sitel.com.mk/rss.xml')
    if status != 200:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    items = []
    for item in root.findall('.//item'):
        link_el = item.find('link')
        date_el = item.find('pubDate')
        if link_el is None or date_el is None:
            continue
        url = link_el.text.strip()
        # Parse pubDate like "Sun, 25 Oct 2026 20:45:43 +0000"
        try:
            dt = datetime.datetime.strptime(date_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
        except ValueError:
            continue
        d = dt.date()
        if START <= d <= END:
            items.append((url, d.isoformat()))
    return items

def fetch_wayback():
    """Query Wayback CDX for all archived URLs in the date window.
    Returns list of (url, date).
    """
    base = 'https://webcache.googleusercontent.com/http://web.archive.org/cdx/search/cdx'
    # Use the official CDX endpoint (no Google cache):
    cdx_url = (
        f'http://web.archive.org/cdx/search/cdx?url=sitel.com.mk/*'
        f'&from=20260925&to=20261025&output=json&fl=original,timestamp'
    )
    status, text, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = eval(text)  # CDX returns JSON array; safe because we control source
    except Exception:
        return []
    results = []
    # first entry is header ['original','timestamp']
    for entry in data[1:]:
        url, ts = entry
        # ts format YYYYMMDDhhmmss
        try:
            dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S')
        except ValueError:
            continue
        d = dt.date()
        if START <= d <= END:
            results.append((url, d.isoformat()))
    return results

def main():
    records = {}
    # First try RSS (fast, reliable dates)
    for url, date in parse_rss():
        records[url] = date
    # If we have fewer than 500 URLs, supplement with Wayback
    if len(records) < 2000:
        for url, date in fetch_wayback():
            if url not in records:
                records[url] = date
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'sitel-com-mk.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, date in sorted(records.items()):
            writer.writerow([url, date])
    # Print per‑day counts
    per_day = {}
    for d in records.values():
        per_day.setdefault(d, 0)
        per_day[d] += 1
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")

if __name__ == '__main__':
    main()
