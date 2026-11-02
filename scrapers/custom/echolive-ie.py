#!/usr/bin/env python3
"""Scraper for The Echo (echolive.ie), window 2026-09-25 .. 2026-10-25.

Route (all via polite_fetch, robots-clean):
  robots.txt advertises https://www.echolive.ie/sitemap-index/398-ee_google_sitemap.xml,
  a quarterly chunk index. The window spans Q3+Q4 2026, so we fetch the two
  quarterly sitemaps directly:
    https://www.echolive.ie/sitemap/398-2026-3-0001.xml  (5331 urls, published 07-01..09-30)
    https://www.echolive.ie/sitemap/398-2026-4-0001.xml  (761 urls, published 10-01..)
  Every <url> carries <news:publication_date> (true publication time) and <lastmod>.
  We use news:publication_date; lastmod is the EDIT time (some Q3 items were
  re-edited in October, Q3 lastmod max 2026-10-22) and is only a fallback for an
  item that has no news block. The listed date is the calendar date as written in
  the site's own timestamp string, no timezone conversion.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

REPO = "."
OUT = os.path.join(REPO, "data/urls_custom/echolive-ie.tsv")
START, END = "2026-09-25", "2026-10-25"

CHUNKS = [
    "https://www.echolive.ie/sitemap/398-2026-3-0001.xml",
    "https://www.echolive.ie/sitemap/398-2026-4-0001.xml",
]

URL_RE = re.compile(r"<url\b[^>]*>(.*?)</url>", re.S)
LOC_RE = re.compile(r"<loc>(.*?)</loc>", re.S)
PUB_RE = re.compile(r"news:publication_date>([^<\s]+)<")
MOD_RE = re.compile(r"<lastmod>([^<\s]+)</lastmod>")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def day_of(ts):
    m = DATE_RE.search(ts or "")
    return m.group(1) if m else None


def main():
    items = {}  # url -> (date, has_news_date)
    for chunk in CHUNKS:
        status, text, _ = fetch(chunk)
        if status != 200 or not text:
            print(f"WARN: {chunk} -> status {status}", file=sys.stderr)
            continue
        n = 0
        for block in URL_RE.findall(text):
            loc = LOC_RE.search(block)
            if not loc:
                continue
            url = loc.group(1).strip()
            pub = PUB_RE.search(block)
            mod = MOD_RE.search(block)
            has_news = pub is not None
            date = day_of(pub.group(1)) if pub else None
            if date is None:
                date = day_of(mod.group(1))
            if date is None or not (START <= date <= END):
                continue
            n += 1
            old = items.get(url)
            if old is None:
                items[url] = (date, has_news)
            else:
                # a news publication date beats a lastmod-derived one
                if has_news and not old[1]:
                    items[url] = (date, True)
        print(f"{chunk}: {status}, {n} in-window urls", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = Counter(d for d, _ in items.values())
    with open(OUT, "w") as f:
        for url in sorted(items):
            f.write(f"{url}\t{items[url][0]}\n")
    print(f"wrote {len(items)} urls to {OUT}")
    for d in sorted(per_day):
        print(f"  {d}: {per_day[d]}")


if __name__ == "__main__":
    main()
