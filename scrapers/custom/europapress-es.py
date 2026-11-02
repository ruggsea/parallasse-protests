#!/usr/bin/env python3
"""List europapress.es article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (permissive) names https://www.europapress.es/sitemap_index/,
which lists per-day sitemaps /sitemap_diario/YYYY-MM-DD/. Each per-day file
holds every URL published that day; every URL ends with a 14-digit
YYYYMMDDHHMMSS publication stamp in Madrid time, which exactly equals the
page's JSON-LD datePublished (verified: URL ...20261020232842.html vs page
datePublished 2026-10-20T23:28:42+02:00). We use that stamp as the listed
date, falling back to the per-day sitemap's own date if a URL has no stamp.
"""
import re
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "https://www.europapress.es"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/europapress-es.tsv"


def day_sitemap_urls(day):
    """Return (url -> date) for one per-day sitemap. {} if not present."""
    url = f"{ROOT}/sitemap_diario/{day.isoformat()}/"
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"  {day}: status {status}", file=sys.stderr)
        return {}
    found = {}
    for m in re.finditer(r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", text):
        loc, lastmod = m.group(1), m.group(2)
        sm = re.search(r"-(\d{14})\.html$", loc)
        if sm:
            d = date(int(sm.group(1)[:4]), int(sm.group(1)[4:6]), int(sm.group(1)[6:8]))
        elif lastmod:
            lm = re.match(r"(\d{4})-(\d{2})-(\d{2})", lastmod)
            d = date(int(lm.group(1)), int(lm.group(2)), int(lm.group(3)))
        else:
            d = day
        found[loc] = d
    return found


def main():
    all_urls = {}
    day = START
    while day <= END:
        found = day_sitemap_urls(day)
        n = 0
        for u, d in found.items():
            if START <= d <= END and u not in all_urls:
                all_urls[u] = d
                n += 1
        print(f"{day}: sitemap gave {len(found)}, new {n}")
        day += timedelta(days=1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as f:
        for u in sorted(all_urls):
            d = all_urls[u]
            f.write(f"{u}\t{d.isoformat()}\n")
            per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]} urls")
    print(f"TOTAL {len(all_urls)} unique URLs -> {OUT}")


if __name__ == "__main__":
    main()
