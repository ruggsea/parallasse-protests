#!/usr/bin/env python3
"""List diariocorreo.pe (Correo, Peru) article URLs published 2026-09-25..2026-10-25.

Route: global per-day archive pages https://diariocorreo.pe/archivo/todas/YYYY-MM-DD/
(one page per day, all sections, no robots restrictions, no per-day pagination).
The date is the archive page's own date (the site's grouping); sampled article pages
carry JSON-LD datePublished on the same calendar day (UTC), within 1 day of the listed date.

Sitemaps (per-section, capped at 100 URLs, ~5 days) and the RSS news feed (100 items,
~1 day) do not cover the window, so the archive pages are the route.
"""
import os
import re
import sys
import datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://diariocorreo.pe"
WINDOW_START = datetime.date(2026, 9, 25)
WINDOW_END = datetime.date(2026, 10, 25)
OUT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "diariocorreo-pe.tsv")
)

ARTICLE_RE = re.compile(r'href="(/[^"]+-noticia/)"')


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    seen = {}
    day_counts = {}
    day = WINDOW_START
    while day <= WINDOW_END:
        url = f"{BASE}/archivo/todas/{day.isoformat()}/"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"day {day}: fetch failed status={status}", file=sys.stderr)
            day += datetime.timedelta(days=1)
            continue
        found = []
        for path in ARTICLE_RE.findall(text):
            full = BASE + path
            if full not in seen:
                seen[full] = day.isoformat()
                found.append(full)
        day_counts[day.isoformat()] = len(found)
        print(f"{day.isoformat()}: +{len(found)} URLs (page status {status})")
        day += datetime.timedelta(days=1)

    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            f.write(f"{url}\t{seen[url]}\n")
    total = sum(day_counts.values())
    print(f"total unique URLs written: {len(seen)} (day hits: {total})")
    missing = [d for d in sorted(day_counts) if day_counts[d] < 15]
    if missing:
        print("WARNING days with <15 URLs:", missing, file=sys.stderr)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
