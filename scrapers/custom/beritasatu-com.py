#!/usr/bin/env python3

"""Scrape article URLs from Berita Satu (beritasatu.com) for the date range
2026-09-25 to 2026-10-25.

The script:
  1. Loads the sitemap index (https://www.beritasatu.com/sitemap.xml).
  2. Retrieves every sub‑sitemap that ends with ``news.xml``.
  3. Parses each ``<url>`` entry, extracts the ``news:publication_date``.
  4. Keeps URLs whose publication date falls inside the target window.
  5. Writes a TSV file ``data/urls_custom/beritasatu-com.tsv`` with lines
     ``URL\tYYYY-MM-DD`` (no header, unique URLs).
  6. Prints a short per‑day count summary.

All HTTP requests use the project's ``polite_fetch`` helper, which respects
robots.txt and rate‑limits.
"""

import os
import sys
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure the project's ``scrapers`` directory (containing ``polite_fetch``) is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SCRAPERS_DIR = os.path.join(PROJECT_ROOT, "scrapers")
sys.path.insert(0, SCRAPERS_DIR)

# ``polite_fetch`` provides a ``fetch`` function returning (status, text, _)
from polite_fetch import fetch

BASE_SITEMAP = "https://www.beritasatu.com/sitemap.xml"
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def fetch_text(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {status}")
    return text

def parse_index(index_xml: str):
    """Yield the location URLs from the sitemap index."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(index_xml)
    for sitemap in root.findall("s:sitemap", ns):
        loc = sitemap.find("s:loc", ns)
        if loc is not None and loc.text:
            yield loc.text.strip()

def parse_news_sitemap(sitemap_xml: str):
    """Yield (url, publication_date) pairs from a news sitemap.
    ``publication_date`` is a ``datetime.date`` instance.
    """
    ns = {
        "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }
    root = ET.fromstring(sitemap_xml)
    for url_el in root.findall("s:url", ns):
        loc_el = url_el.find("s:loc", ns)
        news_pub_el = url_el.find("news:news/news:publication_date", ns)
        if loc_el is None or news_pub_el is None:
            continue
        url = loc_el.text.strip()
        # The date may include time and timezone, e.g. 2026-10-26T12:21:00+07:00
        date_str = news_pub_el.text.split("T")[0]
        try:
            pub_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        yield url, pub_date

def main():
    # Step 1: fetch the index
    index_xml = fetch_text(BASE_SITEMAP)
    # Step 2: collect relevant sub‑sitemaps (news only)
    news_sitemaps = [url for url in parse_index(index_xml) if url.endswith("news.xml")]

    collected = {}
    for sm_url in news_sitemaps:
        try:
            sm_xml = fetch_text(sm_url)
        except Exception as e:
            print(f"[WARN] Skipping sitemap {sm_url}: {e}", file=sys.stderr)
            continue
        for url, pub_date in parse_news_sitemap(sm_xml):
            if START_DATE <= pub_date <= END_DATE:
                # Deduplicate by URL
                collected[url] = pub_date

    # Prepare output directory
    out_path = os.path.join(PROJECT_ROOT, "data", "urls_custom", "beritasatu-com.tsv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Write TSV (sorted by date then URL for reproducibility)
    with open(out_path, "w", encoding="utf-8") as out_f:
        for url, date in sorted(collected.items(), key=lambda kv: (kv[1], kv[0])):
            out_f.write(f"{url}\t{date.isoformat()}\n")

    # Print per‑day counts
    counts = defaultdict(int)
    for d in collected.values():
        counts[d] += 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")
    print(f"Total URLs written: {len(collected)}")

if __name__ == "__main__":
    main()
