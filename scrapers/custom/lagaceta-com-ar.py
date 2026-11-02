#!/usr/bin/env python3
"""Scraper for La Gaceta (Argentina) - lagaceta.com.ar
Collect article URLs published between 2026-09-25 and 2026-10-25.
Uses the per‑day edition sitemaps advertised in robots.txt:
    https://www.lagaceta.com.ar/rss/index_historico.xml
which lists sitemap files at
    https://www.lagaceta.com.ar/rss/index_historico_edicion/<id>.xml
Each edition sitemap contains <url><loc> and <lastmod> entries for the day.
The script respects robots.txt by using the project's ``polite_fetch`` helper.
"""

import sys
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

# Ensure the helper library is on the path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
try:
    from polite_fetch import fetch
except ImportError as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

BASE_URL = "https://www.lagaceta.com.ar"
INDEX_SITEMAP = f"{BASE_URL}/rss/index_historico.xml"
OUT_TSV = "data/urls_custom/lagaceta-com-ar.tsv"
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def fetch_xml(url: str) -> ET.Element:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {status}")
    return ET.fromstring(text)

def parse_index_sitemap(root: ET.Element) -> list:
    """Return list of edition sitemap URLs found in the index sitemap."""
    # The index follows the standard sitemapindex format.
    urls = []
    for sitemap in root.findall('{*}sitemap'):
        loc = sitemap.find('{*}loc')
        if loc is not None and loc.text:
            urls.append(loc.text.strip())
    return urls

def parse_edition_sitemap(root: ET.Element) -> list:
    """Extract (url, lastmod) pairs from an edition sitemap."""
    pairs = []
    for url_el in root.findall('{*}url'):
        loc = url_el.find('{*}loc')
        lastmod = url_el.find('{*}lastmod')
        if loc is None or loc.text is None:
            continue
        url = loc.text.strip()
        date_str = None
        if lastmod is not None and lastmod.text:
            # Accept ISO date or datetime – keep only the date part
            date_str = lastmod.text.strip()[:10]
        else:
            # Fallback: try to infer date from URL path if it contains YYYY/MM/DD
            import re
            m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
            if m:
                date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if date_str:
            pairs.append((url, date_str))
    return pairs

def main():
    # Step 1: fetch the index sitemap that lists per‑day edition sitemaps
    try:
        index_root = fetch_xml(INDEX_SITEMAP)
    except Exception as e:
        sys.stderr.write(f"Error fetching index sitemap: {e}\n")
        sys.exit(1)

    edition_sitemaps = parse_index_sitemap(index_root)
    if not edition_sitemaps:
        sys.stderr.write("No edition sitemaps found in index.\n")
        sys.exit(1)

    # Gather URL -> date mapping, ensuring uniqueness
    url_date = {}
    for s_url in edition_sitemaps:
        try:
            root = fetch_xml(s_url)
        except Exception as e:
            sys.stderr.write(f"Skipping edition sitemap {s_url}: {e}\n")
            continue
        for url, date_str in parse_edition_sitemap(root):
            # Keep only dates within the requested window
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if START <= d <= END:
                if url not in url_date:
                    url_date[url] = date_str
    if not url_date:
        sys.stderr.write("No URLs collected for the requested date range.\n")
        sys.exit(1)

    # Prepare output directory
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", OUT_TSV)
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)

    # Write TSV
    with open(out_path, "w", encoding="utf-8") as f:
        for url, date_str in sorted(url_date.items()):
            f.write(f"{url}\t{date_str}\n")

    # Print per‑day counts
    counts = defaultdict(int)
    for d in url_date.values():
        counts[d] += 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")
    print(f"Total unique URLs written: {len(url_date)}")

if __name__ == "__main__":
    main()
