#!/usr/bin/env python3
"""Scraper for Blic (blic.rs) - collects article URLs published between
2026-09-25 and 2026-10-25 (inclusive) using the monthly sitemaps.

It writes a Tab‑separated file ``data/urls_custom/blic-rs.tsv`` with two
columns: URL and publication date (YYYY‑MM‑DD). The script is meant to be run
stand‑alone (e.g. ``uv run scrapers/custom/blic-rs.py``) and prints a per‑day
summary of how many URLs were written.
"""

import sys
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

# Make sure the polite_fetch helper is on the import path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URLS = [
    "https://www.blic.rs/sitemap-stories-by-month-2026-9.xml.gz",
    "https://www.blic.rs/sitemap-stories-by-month-2026-10.xml.gz",
]

def parse_sitemap(url: str):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"[WARN] Failed to fetch {url} (status {status})", file=sys.stderr)
        return []
    root = ET.fromstring(text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries = []
    for u in root.findall("sm:url", ns):
        loc = u.find("sm:loc", ns).text.strip()
        lm = u.find("sm:lastmod", ns).text.strip()
        # lastmod may contain timezone offset; strip it for ISO parsing
        try:
            dt = datetime.datetime.fromisoformat(lm)
        except ValueError:
            # fallback: drop offset
            dt = datetime.datetime.fromisoformat(lm.split("+")[0].split("-")[0])
        entries.append((loc, dt.date()))
    return entries

def main():
    url_to_date = {}
    for sm_url in SITEMAP_URLS:
        for loc, pub_date in parse_sitemap(sm_url):
            if START <= pub_date <= END:
                # keep the first encountered date (should be unique)
                url_to_date.setdefault(loc, pub_date)
    # write TSV
    out_path = Path(__file__).resolve().parents[2] / "data" / "urls_custom" / "blic-rs.tsv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fout:
        for url, d in sorted(url_to_date.items()):
            fout.write(f"{url}\t{d.isoformat()}\n")
    # summary per day
    counts = {}
    for d in url_to_date.values():
        counts.setdefault(d, 0)
        counts[d] += 1
    for d in sorted(counts):
        print(f"{d}: {counts[d]} URLs")
    print(f"Wrote {len(url_to_date)} unique URLs to {out_path}")

if __name__ == "__main__":
    main()
