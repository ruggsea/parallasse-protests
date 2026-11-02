#!/usr/bin/env python3
"""Scrape article URLs from Večernje novosti (novosti.rs) for the date range
2026-09-25 to 2026-10-25.
Writes a TSV file with columns: URL<TAB>YYYY-MM-DD (publication date).
Uses the site's news sitemap which provides <news:publication_date>.
All HTTP requests go through polite_fetch.fetch.
"""

import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Add the scraper directory to sys.path so polite_fetch can be imported.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch module not found\n")
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
SITEMAP_URL = "https://www.novosti.rs/sitemaps/xml/news"

def iso_to_date(iso_str: str) -> datetime.date:
    # iso example: 2026-10-26T08:36:00+01:00
    try:
        dt = datetime.datetime.fromisoformat(iso_str.rstrip('Z'))
    except ValueError:
        # fallback split
        dt = datetime.datetime.strptime(iso_str[:10], "%Y-%m-%d")
    return dt.date()

def main():
    status, text, _ = fetch(SITEMAP_URL)
    if status != 200:
        sys.stderr.write(f"Failed to fetch sitemap, status {status}\n")
        sys.exit(1)
    # Parse XML – handle namespaces
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    root = ET.fromstring(text)
    urls = []
    seen = set()
    per_day = {}
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        date_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or date_el is None:
            continue
        url = loc_el.text.strip()
        pub_date = iso_to_date(date_el.text.strip())
        if pub_date < START or pub_date > END:
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append((url, pub_date.isoformat()))
        per_day[pub_date] = per_day.get(pub_date, 0) + 1
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "novosti-rs.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for url, date_str in sorted(urls, key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{date_str}\n")
    # Print summary
    total = len(urls)
    sys.stdout.write(f"Wrote {total} URLs to {out_path}\n")
    for day in sorted(per_day):
        sys.stdout.write(f"{day}: {per_day[day]}\n")

if __name__ == "__main__":
    main()
