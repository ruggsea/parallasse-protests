#!/usr/bin/env python3
"""Trouw (trouw.nl) custom scraper.

Window: 2026-09-25 .. 2026-10-25.
Route: robots.txt (User-agent: * Allow: /) names the sitemap
https://www.trouw.nl/sitemap.xml, a sitemap index with per-month urlsets
(sitemaps/YYYYMM.xml). We take the two months covering the window
(202609, 202610) and list every URL whose <lastmod> date-part falls inside
the window. Verified on sample articles that <lastmod> equals the page
JSON-LD datePublished to the second for the majority of URLs (DPG stamps
lastmod from publish time; some URLs get a later batch update at most a day
or so after publication).
"""
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "."
OUT = os.path.join(BASE, "data", "urls_custom", "trouw-nl.tsv")
START, END = "2026-09-25", "2026-10-25"

MONTHS = ["202609", "202610"]


def main():
    found = {}  # url -> date
    per_day = {}
    for mm in MONTHS:
        status, text, _ = fetch(f"https://www.trouw.nl/sitemaps/{mm}.xml")
        if status != 200:
            print(f"FAIL {mm}.xml status={status}")
            continue
        for m in re.finditer(
            r"<loc>\s*(https://www\.trouw\.nl/[^<\s]+?)\s*</loc>"
            r"(?:.*?<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})[T0-9:.]*Z?\s*</lastmod>)?",
            text,
            re.S,
        ):
            url, lastmod = m.group(1), m.group(2)
            if lastmod and START <= lastmod <= END:
                if url not in found:
                    found[url] = lastmod
                    per_day[lastmod] = per_day.get(lastmod, 0) + 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(found):
            f.write(f"{url}\t{found[url]}\n")
    print(f"wrote {len(found)} urls to {OUT}")
    for d in sorted(per_day):
        print(d, per_day[d])
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("target", d, per_day.get(d, 0))


if __name__ == "__main__":
    main()
