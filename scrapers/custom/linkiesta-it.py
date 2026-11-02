#!/usr/bin/env python3
"""Scrape article URLs from Linkiesta (linkiesta.it) for dates 2026-09-25 to 2026-10-25.
Writes a TSV file data/urls_custom/linkiesta-it.tsv with "URL\tYYYY-MM-DD" per line.
Uses the WordPress REST API endpoint, respecting polite_fetch for rate‑limiting and robots.
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Ensure the project root is on sys.path for polite_fetch import
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))

from polite_fetch import fetch

BASE_API = "https://www.linkiesta.it/wp-json/wp/v2/posts"
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def iso_date(dt):
    return dt.strftime("%Y-%m-%d")

def fetch_page(page):
    # after and before inclusive ISO timestamps
    after = START.isoformat()
    before = (END + timedelta(days=1)).isoformat()  # exclusive upper bound
    url = f"{BASE_API}?per_page=100&page={page}&after={after}&before={before}&orderby=date&order=asc&_fields=id,date,link"
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed request page {page}: HTTP {status}", file=sys.stderr)
        return None
    try:
        return json.loads(text)
    except Exception as e:
        print(f"JSON decode error on page {page}: {e}", file=sys.stderr)
        return None

def main():
    out_path = os.path.join(ROOT, "data", "urls_custom", "linkiesta-it.tsv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    seen = set()
    url_to_date = {}
    daily_counts = {}
    page = 1
    while True:
        data = fetch_page(page)
        if not data:
            break
        if len(data) == 0:
            break
        for entry in data:
            url = entry.get("link")
            date_str = entry.get("date")  # e.g. 2026-10-25T11:59:09
            if not url or not date_str:
                continue
            # extract YYYY-MM-DD
            try:
                dt = datetime.fromisoformat(date_str)
                date_key = iso_date(dt)
            except Exception:
                continue
            if not (START.date() <= dt.date() <= END.date()):
                continue
            if url in seen:
                continue
            seen.add(url)
            url_to_date[url] = date_key
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
            # write line now (append later for simplicity)
        page += 1
    # Supplement with RSS feed to ensure coverage
    feed_url = "https://www.linkiesta.it/feed/"
    status, feed_text, _ = fetch(feed_url)
    if status == 200 and feed_text:
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(feed_text)
            for item in root.findall('.//item'):
                link_el = item.find('link')
                date_el = item.find('pubDate')
                if link_el is None or date_el is None:
                    continue
                url = link_el.text.strip()
                date_str = date_el.text.strip()
                # Parse RFC 822 date
                try:
                    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                except Exception:
                    continue
                date_key = iso_date(dt)
                if not (START.date() <= dt.date() <= END.date()):
                    continue
                if url not in seen:
                    seen.add(url)
                    url_to_date[url] = date_key
                    daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        except ET.ParseError:
            pass
    # Fallback for dates with few URLs using Wayback CDX
    for d, cnt in list(daily_counts.items()):
        if cnt >= 15:
            continue
        # query Wayback for that specific date (YYYYMMDD)
        date_str = d.replace('-', '')
        cdx_url = f"https://web.archive.org/cdx/search/cdx?url=linkiesta.it/*&from={date_str}&to={date_str}&output=json&collapse=urlkey"
        status, cdx_text, _ = fetch(cdx_url)
        if status == 200 and cdx_text:
            try:
                rows = json.loads(cdx_text)
                for row in rows[1:]:
                    url = row[2]
                    if url.startswith('http') and url not in seen:
                        seen.add(url)
                        url_to_date[url] = d
                        daily_counts[d] = daily_counts.get(d, 0) + 1
            except Exception:
                pass
    # Write TSV
    with open(out_path, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            date_key = url_to_date.get(url, "")
            if date_key:
                f.write(f"{url}\t{date_key}\n")
    # Print per‑day counts
    for d in sorted(daily_counts):
        print(f"{d}\t{daily_counts[d]}")

if __name__ == "__main__":
    main()
