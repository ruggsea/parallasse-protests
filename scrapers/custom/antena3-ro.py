#!/usr/bin/env python3
"""Antena 3 (Romania) article URL scraper for 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
- robots.txt permissive (Allow: /), names sitemaps.
- https://www.antena3.ro/sitemap.xml is an index of monthly article
  sitemaps sitemap-articles-YYYY-MM.xml (full urlsets with <lastmod>
  timestamps on every entry).
- <lastmod> IS the publication time: on sampled articles it matches the
  page JSON-LD NewsArticle datePublished to the minute (one sample off by
  3 min, same date). dateModified can be later, so do not use it.
- Listed date = date-part of <lastmod> (Bucharest local, +03:00/+02:00 in
  the window).
- Video URLs (/videos-antena3-cnn/) are excluded: article pages only.
"""
import os
import re
import sys
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.antena3.ro"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/antena3-ro.tsv"

URL_RE = re.compile(r"<url>\s*<loc>(.*?)</loc>.*?</url>", re.S)
LM_RE = re.compile(r"<lastmod>(\d{4}-\d{2}-\d{2})")


def main():
    seen = {}  # url -> iso date
    for month in ("2026-09", "2026-10"):
        url = f"{BASE}/sitemap-articles-{month}.xml"
        status, text, _ = fetch(url)
        if status != 200:
            print(f"ERROR {url} -> {status}", file=sys.stderr)
            continue
        for m in URL_RE.finditer(text):
            loc = m.group(1).strip()
            if "/videos-antena3-cnn/" in loc:
                continue
            lm = LM_RE.search(m.group(0))
            if not lm:
                continue
            d = date.fromisoformat(lm.group(1))
            if not (START <= d <= END):
                continue
            if loc not in seen:
                seen[loc] = d.isoformat()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w") as f:
        for loc, iso in sorted(seen.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{loc}\t{iso}\n")
            per_day[iso] = per_day.get(iso, 0) + 1
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"TOTAL {len(seen)} urls -> {OUT}")


if __name__ == "__main__":
    main()
