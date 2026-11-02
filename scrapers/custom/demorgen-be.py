#!/usr/bin/env python3
"""Scrape De Morgen article URLs for 2026-09-25 to 2026-10-25.
Writes TSV with URL and publication date (YYYY-MM-DD) to
data/urls_custom/demorgen-be.tsv (relative to project root).
Uses the site's monthly sitemaps (e.g. /sitemaps/202609.xml).
All HTTP requests go through polite_fetch to respect robots.txt.
"""
import sys
import os
import csv
import datetime
import xml.etree.ElementTree as ET

# Add the scrapers directory to sys.path so polite_fetch can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from polite_fetch import fetch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_TSV = os.path.join(PROJECT_ROOT, "data", "urls_custom", "demorgen-be.tsv")

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def fetch_month_sitemap(year_month: str):
    """Fetch a monthly sitemap like '202609' and return list of (url, date).
    The sitemap uses <url><loc> and <lastmod> tags.
    """
    url = f"https://www.demorgen.be/sitemaps/{year_month}.xml"
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch {url}: status {status}")
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error for {url}: {e}")
        return []
    entries = []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod = lastmod_el.text.strip()[:10]  # YYYY-MM-DD
        try:
            pub_date = datetime.datetime.strptime(lastmod, "%Y-%m-%d").date()
        except ValueError:
            continue
        if START_DATE <= pub_date <= END_DATE:
            entries.append((loc, pub_date))
    return entries

def main():
    all_entries = []
    for ym in ["202609", "202610"]:
        all_entries.extend(fetch_month_sitemap(ym))
    # Deduplicate URLs, keep first seen date
    uniq = {}
    for url, d in all_entries:
        if url not in uniq:
            uniq[url] = d
    # Sort by date then URL
    sorted_items = sorted(uniq.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        for url, d in sorted_items:
            writer.writerow([url, d.isoformat()])
    # Print per‑day counts
    counts = {}
    for _, d in sorted_items:
        counts.setdefault(d, 0)
        counts[d] += 1
    for d in sorted(counts):
        print(f"{d}: {counts[d]} URLs")

if __name__ == "__main__":
    main()
