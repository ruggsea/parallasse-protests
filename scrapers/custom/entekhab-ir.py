#!/usr/bin/env python3
"""Scrape article URLs and publication dates from entekhab.ir for the date range
2026-09-25 to 2026-10-25.

Uses the site's sitemap index (fa-sitemap-newsarchive) which lists per‑month
archive sitemaps. We fetch the recent 1405‑* sitemaps (Persian year 1405 ≈
2026 Gregorian) and extract <loc> and <lastmod> entries. Only entries whose
date falls in the target window are kept.

Outputs a TSV file `data/urls_custom/entekhab-ir.tsv` with columns:
    URL<TAB>YYYY-MM-DD
One line per article, deduplicated, no header.
The script also prints per‑day counts to stdout.
"""

import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Ensure the project root (two levels up) is on PYTHONPATH so that
# `polite_fetch` can be imported when this script runs in isolation.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from polite_fetch import fetch  # assumed to be available in the environment

INDEX_URL = "https://www.entekhab.ir/fa-sitemap-newsarchive"
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_text(url: str) -> str:
    """Fetch a URL and return the response text using polite_fetch.fetch."""
    resp = fetch(url, timeout=30)
    # polite_fetch may return a Response‑like object with .text attribute
    if isinstance(resp, str):
        return resp
    return getattr(resp, "text", str(resp))


def parse_sitemap(url: str):
    """Yield (article_url, date_str) pairs from a sitemap XML.
    date_str is in YYYY‑MM‑DD format extracted from <lastmod>.
    """
    txt = fetch_text(url)
    root = ET.fromstring(txt)
    for url_el in root.findall("s:url", NS):
        loc_el = url_el.find("s:loc", NS)
        lastmod_el = url_el.find("s:lastmod", NS)
        if loc_el is None or lastmod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod = lastmod_el.text.strip()
        date_part = lastmod.split("T")[0]
        yield loc, date_part


def main():
    urls_by_date: dict[str, set[str]] = {}

    # Fetch the index sitemap and iterate over per‑month sitemaps
    index_txt = fetch_text(INDEX_URL)
    index_root = ET.fromstring(index_txt)
    for sm_el in index_root.findall("s:sitemap", NS):
        loc_el = sm_el.find("s:loc", NS)
        if loc_el is None:
            continue
        sitemap_url = loc_el.text.strip()
        # Focus on the current Persian year (1405) which maps to 2026
        if "1405-" not in sitemap_url:
            continue
        for article_url, date_str in parse_sitemap(sitemap_url):
            try:
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if START_DATE <= d <= END_DATE:
                urls_by_date.setdefault(date_str, set()).add(article_url)

    # Write deduplicated TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "urls_custom", "entekhab-ir.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out_f:
        for date in sorted(urls_by_date):
            for url in sorted(urls_by_date[date]):
                out_f.write(f"{url}\t{date}\n")

    # Print per‑day counts
    for date in sorted(urls_by_date):
        print(f"{date}\t{len(urls_by_date[date])}")


if __name__ == "__main__":
    main()
