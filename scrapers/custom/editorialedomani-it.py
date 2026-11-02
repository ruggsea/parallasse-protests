#!/usr/bin/env python3
"""Scrape editorialedomani.it article URLs for the window 2026-09-25 → 2026-10-25.

We use two sources, both respecting ``polite_fetch``:

1. The news sitemap (``sitemap_news1.xml``) which provides ``<news:publication_date>``
   for each article. This covers the most recent days.
2. Section listing pages (e.g. ``/politica``, ``/economia`` …).  Each page embeds a
   GraphQL payload inside ``<script id="__NEXT_DATA__">``.  The helper ``parse_domani.listing``
   extracts ``(path, iso_date)`` pairs from that payload.

All URLs whose publication date falls within the inclusive window are written to
``data/urls_custom/editorialedomani-it.tsv`` as ``URL<TAB>YYYY-MM-DD`` (no header).
Duplicates are removed.  The script prints a per‑day count to stdout.
"""

import sys
import os
from collections import Counter
from datetime import datetime

# Make ``polite_fetch`` importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

# Helper for the sitemap route
import xml.etree.ElementTree as ET

BASE_SITEMAP = "https://www.editorialedomani.it/sitemaps/sitemap_news1.xml"
START = "2026-09-25"
END = "2026-10-25"
OUTPUT_TSV = "data/urls_custom/editorialedomani-it.tsv"

# Sections to crawl (same list used by earlier exploratory scripts)
SECTIONS = [
    "/politica", "/fatti", "/economia", "/ambiente", "/giustizia", "/idee",
    "/inchieste", "/sport", "/cibo", "/blog-mafie", "/podcast", "/video",
]
BASE = "https://www.editorialedomani.it"

# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------

def _parse_sitemap(xml_text: str):
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9", "news": "http://www.google.com/schemas/sitemap-news/0.9"}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}
    out = {}
    for url_el in root.findall("ns:url", ns):
        loc = url_el.find("ns:loc", ns)
        pub = url_el.find("news:news/news:publication_date", ns)
        if loc is None or pub is None or not loc.text or not pub.text:
            continue
        date = pub.text[:10]
        if START <= date <= END:
            out[loc.text.strip()] = date
    return out

# ---------------------------------------------------------------------------
# Section page parsing – reuse existing ``parse_domani`` helper
# ---------------------------------------------------------------------------
from parse_domani import listing

def _crawl_sections():
    collected = {}
    for sec in SECTIONS:
        for pg in range(1, 31):  # arbitrary limit; we break earlier when dates are older than START
            url = BASE + sec + ("" if pg == 1 else f"?page={pg}")
            status, html, _ = fetch(url)
            if status != 200 or not html:
                break
            _, rows = listing(html)
            if not rows:
                break
            new_this_page = 0
            for row in rows:
                path = row[0]
                iso_date = row[1]
                day = iso_date[:10]
                if START <= day <= END:
                    full_url = BASE + path
                    if full_url not in collected:
                        collected[full_url] = day
                        new_this_page += 1
            # Determine the oldest date on this page to decide when to stop
            oldest = min((r[1][:10] for r in rows), default="9999-12-31")
            if oldest < START:
                break
    return collected

# ---------------------------------------------------------------------------
def main():
    # 1. Sitemap source
    sitemap_results = {}
    st, txt, _ = fetch(BASE_SITEMAP)
    if st == 200 and txt:
        sitemap_results = _parse_sitemap(txt)

    # 2. Section listings fallback
    section_results = _crawl_sections()

    # Merge, preferring sitemap date (they are the same ISO date format)
    merged = dict(section_results)
    merged.update(sitemap_results)  # sitemap may overwrite with same URL/date

    if not merged:
        print("No articles found in the requested window.")
        sys.exit(0)

    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for url in sorted(merged):
            f.write(f"{url}\t{merged[url]}\n")

    # Print per‑day counts
    cnt = Counter(merged.values())
    for d in sorted(cnt):
        print(f"{d}\t{cnt[d]}")

if __name__ == "__main__":
    main()
