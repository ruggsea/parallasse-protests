#!/usr/bin/env python3
"""Liputan6.com scraper
Collect article URLs published between 2026-09-25 and 2026-10-25.
Writes a TSV ``data/urls_custom/liputan6-com.tsv`` with ``URL<TAB>YYYY-MM-DD``.
Uses the site‑wide sitemap index (https://www.liputan6.com/sitemap.xml).
Falls back to each section’s ``sitemap-news.xml`` if present.
All HTTP requests go through ``polite_fetch.fetch`` as required.
"""

import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# make polite_fetch importable (project‑relative path)
sys.path.insert(0, "scrapers")
# The repository adds a helper package at scrapers/ that contains polite_fetch
# (the path is scrapers)
# Ensure we can import it.
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
START_DATE = datetime.date(2026, 9, 25)
END_DATE   = datetime.date(2026, 10, 25)

# Output location – relative to repository root
TSV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "liputan6-com.tsv"))

# Main sitemap index
MAIN_SITEMAP = "https://www.liputan6.com/sitemap.xml"

# ---------------------------------------------------------------------------

def iso_to_date(iso_str: str) -> datetime.date:
    """Convert an ISO‑8601 string (with optional timezone) to a date object.
    ``2026-10-25T21:10:58+07:00`` -> datetime.date(2026, 10, 25)"""
    # split at 'T' and take the date part
    date_part = iso_str.split('T')[0]
    return datetime.datetime.strptime(date_part, "%Y-%m-%d").date()


def fetch_xml(url: str) -> ET.Element:
    """Fetch a URL with polite_fetch and parse the XML content.
    Returns the root element or raises on error."""
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {status}")
    return ET.fromstring(text)


def collect_sitemap_urls(sitemap_url: str) -> list[tuple[str, datetime.date]]:
    """Parse a sitemap (or sitemap index) and return a list of (url, date).
    Handles both ``<urlset>`` and ``<sitemapindex>`` structures.
    """
    root = fetch_xml(sitemap_url)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    items = []
    if root.tag.endswith('sitemapindex'):
        # recurse into each child sitemap
        for sm in root.findall('sm:sitemap', ns):
            loc = sm.find('sm:loc', ns)
            if loc is None or not loc.text:
                continue
            items.extend(collect_sitemap_urls(loc.text.strip()))
    elif root.tag.endswith('urlset'):
        for url_el in root.findall('sm:url', ns):
            loc_el = url_el.find('sm:loc', ns)
            lastmod_el = url_el.find('sm:lastmod', ns)
            if loc_el is None or loc_el.text is None:
                continue
            url = loc_el.text.strip()
            # Some sitemaps omit lastmod – skip those
            if lastmod_el is None or lastmod_el.text is None:
                continue
            try:
                pub_date = iso_to_date(lastmod_el.text.strip())
            except Exception:
                continue
            items.append((url, pub_date))
    else:
        # unknown structure – ignore
        pass
    return items


def main():
    # Gather all sitemap URLs from the main index
    try:
        root = fetch_xml(MAIN_SITEMAP)
    except Exception as e:
        sys.stderr.write(f"Could not fetch main sitemap index: {e}\n")
        sys.exit(1)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = []
    for sm in root.findall('sm:sitemap', ns):
        loc = sm.find('sm:loc', ns)
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text.strip())
    # Ensure we also include any news‑specific sitemaps that may not be listed
    # (the index already contains them, but we keep the list as‑is).

    unique = {}
    for sm_url in sitemap_urls:
        try:
            for url, pub_date in collect_sitemap_urls(sm_url):
                if START_DATE <= pub_date <= END_DATE:
                    if url not in unique:
                        unique[url] = pub_date
        except Exception as e:
            sys.stderr.write(f"Error processing sitemap {sm_url}: {e}\n")
            continue
    # Prepare output directory
    out_dir = os.path.dirname(TSV_PATH)
    os.makedirs(out_dir, exist_ok=True)

    # Write TSV sorted by date then URL
    with open(TSV_PATH, "w", encoding="utf-8") as f:
        for url, d in sorted(unique.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{url}\t{d.isoformat()}\n")

    # Print per‑day counts for quick inspection
    per_day = defaultdict(int)
    for d in unique.values():
        per_day[d.isoformat()] += 1
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")
    print(f"Total URLs written: {len(unique)}")

if __name__ == "__main__":
    main()
