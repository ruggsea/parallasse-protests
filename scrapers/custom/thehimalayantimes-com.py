#!/usr/bin/env python3
"""Scrape article URLs from The Himalayan Times for 2026-09-25 to 2026-10-25.
Uses the site's public XML sitemaps and polite_fetch for all HTTP requests.
Writes a TSV file with URL and ISO date (YYYY-MM-DD) – no header, unique URLs.
"""
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure the repository's scraper path is on sys.path for polite_fetch import
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(BASE_DIR, 'scrapers'))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def fix_loc(loc: str) -> str:
    """Clean malformed loc entries like
    https://thehimalayantimes.com/https://thehimalayantimes.com/..."""
    prefix = "https://thehimalayantimes.com/"
    if loc.startswith(prefix + prefix):
        return loc[len(prefix):]
    return loc

def parse_sitemap(url: str, results):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch {url}: status {status}\n")
        return
    # Parse XML
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        sys.stderr.write(f"XML parse error for {url}: {e}\n")
        return
    # Namespace handling – sitemap may use default ns
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        date_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or date_el is None:
            continue
        loc = fix_loc(loc_el.text.strip())
        lastmod = date_el.text.strip()
        # Extract date part
        try:
            dt = datetime.fromisoformat(lastmod)
        except ValueError:
            # fallback split
            dt = datetime.strptime(lastmod[:10], "%Y-%m-%d")
        if START.date() <= dt.date() <= END.date():
            results[dt.date()].add(loc)

def main():
    results = {}
    for single_date in (START + timedelta(days=i) for i in range((END-START).days + 1)):
        results[single_date.date()] = set()

    months = [(2026, 9), (2026, 10)]
    for year, month in months:
        sitemap_url = f"https://thehimalayantimes.com//sitemaps/{year}/{month}/sitemap_0.xml"
        parse_sitemap(sitemap_url, results)

    # Write TSV
    out_path = os.path.join(BASE_DIR, 'data', 'urls_custom', 'thehimalayantimes-com.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total_written = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for day in sorted(results):
            urls = sorted(results[day])
            for url in urls:
                f.write(f"{url}\t{day.isoformat()}\n")
                total_written += 1
    # Print simple stats
    print(f"Wrote {total_written} URLs total.")
    for day in sorted(results):
        print(f"{day}: {len(results[day])} URLs")

if __name__ == "__main__":
    main()
