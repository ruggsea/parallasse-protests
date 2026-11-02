#!/usr/bin/env python3

"""Scraper for El Telégrafo (Ecuador).
Collect article URLs published between 2026-09-25 and 2026-10-25 (inclusive)
using the public sitemap(s) advertised in robots.txt.
The script respects robots.txt by using the project's ``polite_fetch`` helper.
Output is written to ``data/urls_custom/eltelegrafo-com-ec.tsv`` with two
columns: URL<TAB>YYYY-MM-DD (the publication date taken from the sitemap's
news:publication_date element).
"""

import sys
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure the helper module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scrapers")))
try:
    from polite_fetch import fetch
except ImportError:
    print("polite_fetch module not found", file=sys.stderr)
    sys.exit(1)

BASE_SITEMAP = "https://www.eltelegrafo.com.ec/component/route66/sitemap/1/k2?format=xml"
START_DATE = datetime(2026, 9, 25).date()
END_DATE = datetime(2026, 10, 25).date()
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "eltelegrafo-com-ec.tsv"))

def fetch_sitemap(page: int = None):
    """Fetch a sitemap page. ``page`` is appended as ``&page=N`` if given.
    Returns the raw XML text or ``None`` on HTTP error.
    """
    url = BASE_SITEMAP
    if page is not None:
        url = f"{BASE_SITEMAP}&page={page}"
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch {url}: HTTP {status}", file=sys.stderr)
        return None
    return text

def parse_sitemap(xml_text: str):
    """Parse sitemap XML and yield (url, pub_date) tuples.
    ``pub_date`` is a ``date`` instance.
    """
    # Register the news namespace used in the sitemap
    ns = {"news": "http://www.google.com/schemas/sitemap-news/0.9"}
    root = ET.fromstring(xml_text)
    for url_el in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        loc_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        # publication date may be inside news:news/news:publication_date
        pub_el = url_el.find("news:news/news:publication_date", ns)
        if pub_el is None or not pub_el.text:
            continue
        # Example format: 2026-10-24T00:00:00-05:00
        dt = datetime.fromisoformat(pub_el.text.strip())
        pub_date = dt.date()
        yield url, pub_date

def main():
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    seen = set()
    url_to_date = {}
    per_day_counts = {}
    page = 1
    while True:
        xml = fetch_sitemap(page if page > 1 else None)
        if not xml:
            break
        added = 0
        for url, pub_date in parse_sitemap(xml):
            if pub_date < START_DATE or pub_date > END_DATE:
                continue
            if url in seen:
                continue
            seen.add(url)
            url_to_date[url] = pub_date
            per_day_counts.setdefault(pub_date, 0)
            per_day_counts[pub_date] += 1
            added += 1
        if added == 0:
            break
        page += 1
        time.sleep(1)

    # Write TSV sorted by date then URL
    with open(OUTPUT_TSV, "w", encoding="utf-8") as out_f:
        for pub_date in sorted(per_day_counts):
            day_urls = [u for u, d in url_to_date.items() if d == pub_date]
            for u in sorted(day_urls):
                out_f.write(f"{u}\t{pub_date.isoformat()}\n")
            print(f"{pub_date}: {per_day_counts[pub_date]} URLs written")

if __name__ == "__main__":
    main()
