#!/usr/bin/env python3
"""Scrape article URLs from The Nation (Nigeria) within a date window.

Outputs a TSV file with URL and publication date (YYYY-MM-DD).
Uses the site's post sitemaps discovered via the sitemap index.
Dates are taken from the <lastmod> field, which corresponds to the
publication date for this site.
"""
import sys
import os
import re
import datetime
import xml.etree.ElementTree as ET

# Add the scrapers directory to the import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from polite_fetch import fetch

BASE_URL = "https://thenationonlineng.net"
SITEMAP_INDEX = f"{BASE_URL}/sitemap_index.xml"
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/urls_custom/thenationonlineng-net.tsv"))

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def iso_to_date(iso: str) -> datetime.date:
    # Handles strings like 2026-10-17T05:10:15+00:00
    return datetime.datetime.fromisoformat(iso.rstrip('Z')).date()

def fetch_sitemap_urls():
    status, text, _ = fetch(SITEMAP_INDEX)
    if status != 200:
        print(f"Failed to fetch sitemap index: {status}")
        sys.exit(1)
    locs = re.findall(r'<loc>(.*?)</loc>', text)
    # keep only post‑sitemap files
    post = [u for u in locs if re.search(r'post-sitemap\d*\.xml$', u)]
    # sort by numeric suffix descending (newest first)
    def key(url):
        m = re.search(r'post-sitemap(\d*)\.xml', url)
        return int(m.group(1)) if m and m.group(1).isdigit() else 0
    post.sort(key=key, reverse=True)
    return post

def parse_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Could not fetch {url}: {status}")
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error in {url}: {e}")
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        mod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or mod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod = mod_el.text.strip()
        try:
            pub_date = iso_to_date(lastmod)
        except Exception:
            continue
        if START <= pub_date <= END:
            entries.append((loc, pub_date.isoformat()))
        elif pub_date < START:
            # older than window – signal to stop further sitemaps
            return None
    return entries

def main():
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    collected = []  # list of (url, date)
    seen = set()
    for sitemap_url in fetch_sitemap_urls():
        result = parse_sitemap(sitemap_url)
        if result is None:
            break  # reached dates older than START
        for loc, date_str in result:
            if loc not in seen:
                seen.add(loc)
                collected.append((loc, date_str))
    # write TSV sorted by date then URL
    collected.sort(key=lambda x: (x[1], x[0]))
    with open(OUT_TSV, "w", encoding="utf-8") as out_f:
        for url, date_str in collected:
            out_f.write(f"{url}\t{date_str}\n")
    # print per‑day counts
    from collections import Counter
    counts = Counter(date for _, date in collected)
    for d in sorted(counts):
        print(f"{d}: {counts[d]} URLs")
    print(f"Wrote {len(collected)} URLs to {OUT_TSV}")

if __name__ == "__main__":
    main()
