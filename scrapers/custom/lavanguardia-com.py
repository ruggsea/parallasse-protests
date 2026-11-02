#!/usr/bin/env python3
"""Scrape La Vanguardia article URLs for a given date window.

Uses the Google News sitemap which provides <news:publication_date> for each
article. The script fetches the sitemap via the project's ``polite_fetch``
helper, extracts URLs whose publication date falls between 2026-09-25 and
2026-10-25 (inclusive) and writes them to ``data/urls_custom/lavanguardia-com.tsv``
as ``URL<TAB>YYYY-MM-DD`` (no header). Duplicates are removed.
"""

import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone

# Ensure the project's scraper helpers are on the import path
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

SITEMAP_URL = "https://www.lavanguardia.com/sitemap-google-news.xml"
START_DATE = date(2026, 9, 25)
END_DATE = date(2026, 10, 25)

OUTPUT_TSV = "data/urls_custom/lavanguardia-com.tsv"

def fetch_sitemap(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: HTTP {status}")
    return text

def parse_sitemap(xml_content: str):
    # Use iterparse for low memory usage
    for event, elem in ET.iterparse(sys.stdin if xml_content is None else ET.fromstring(xml_content), events=("end",)):
        pass

def main():
    # Fetch sitemap
    sitemap_xml = fetch_sitemap(SITEMAP_URL)

    # Parse XML – the sitemap can be large, so use iterparse on a string buffer
    # Build a set of (url, date) tuples
    results = set()
    # Namespace handling
    ns = {
        "ns": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }
    # iterparse from string via BytesIO
    import io
    it = ET.iterparse(io.BytesIO(sitemap_xml.encode("utf-8")), events=("end",))
    for event, elem in it:
        if elem.tag.endswith('url'):
            loc_el = elem.find('ns:loc', ns)
            pub_el = elem.find('news:news/news:publication_date', ns)
            if loc_el is not None:
                url = loc_el.text.strip()
                pub_date = None
                if pub_el is not None:
                    try:
                        pub_dt = datetime.fromisoformat(pub_el.text.strip())
                        pub_date = pub_dt.date()
                    except Exception:
                        pub_date = None
                # Fallback: extract YYYYMMDD from URL path
                if pub_date is None:
                    import re
                    m = re.search(r"/(\d{8})/", url)
                    if m:
                        try:
                            pub_date = datetime.strptime(m.group(1), "%Y%m%d").date()
                        except Exception:
                            pub_date = None
                if pub_date and START_DATE <= pub_date <= END_DATE:
                    results.add((url, pub_date.isoformat()))
            # clear to free memory
            elem.clear()
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    # Write TSV, sorted by date then URL
    with open(OUTPUT_TSV, "w", encoding="utf-8") as out:
        for url, d in sorted(results, key=lambda x: (x[1], x[0])):
            out.write(f"{url}\t{d}\n")
    # Print a summary per day
    from collections import Counter
    cnt = Counter(d for _, d in results)
    for d in sorted(cnt):
        print(f"{d}: {cnt[d]} URLs")

if __name__ == "__main__":
    main()
