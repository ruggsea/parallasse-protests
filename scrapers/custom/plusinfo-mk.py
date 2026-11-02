#!/usr/bin/env python3
"""Scrape plusinfo.mk (North Macedonia) article URLs published 2026-09-25..2026-10-25.

Route: WP REST API /wp-json/wp/v2/posts with date range (site is WordPress + Yoast;
robots.txt allows /wp-json/). The API returns each post's `link` and `date`
(site-local publication time). Verified: the API `date` matches the date the
article page displays (e.g. 25/10/2026) and its JSON-LD datePublished (same
moment, UTC offset +01:00 for the site).

post-sitemap.xml is NOT usable for dates: Yoast lastmod is edit time (a
2020-era article re-edited in 2026) and slugs carry no date.

Output: data/urls_custom/plusinfo-mk.tsv, one line URL<TAB>YYYY-MM-DD, unique URLs.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/plusinfo-mk.tsv"
API = "https://plusinfo.mk/wp-json/wp/v2/posts"
AFTER = "2026-09-25T00:00:00"
BEFORE = "2026-10-26T00:00:00"  # exclusive end: covers 2026-10-25
PER_PAGE = 100


def main():
    posts = {}
    page = 1
    while True:
        url = (f"{API}?after={AFTER}&before={BEFORE}"
               f"&per_page={PER_PAGE}&page={page}&orderby=date&order=desc")
        status, text, _ = fetch(url)
        if status == 429:  # rate limited: back off and retry once more
            time.sleep(30)
            status, text, _ = fetch(url)
        if status != 200:
            sys.exit(f"REST API failed on page {page}: status {status}")
        try:
            batch = json.loads(text)
        except json.JSONDecodeError:
            sys.exit(f"REST API returned non-JSON on page {page}")
        if not isinstance(batch, list) or not batch:
            break
        for p in batch:
            link = p.get("link")
            date = (p.get("date") or "")[:10]
            if link and len(date) == 10:
                posts.setdefault(link, date)
        if len(batch) < PER_PAGE:
            break
        page += 1
        if page > 200:  # safety cap: 20k posts
            break

    rows = sorted({(d, u) for u, d in posts.items()})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for date, u in rows:
            f.write(f"{u}\t{date}\n")

    per_day = {}
    for u, d in posts.items():
        per_day[d] = per_day.get(d, 0) + 1
    total = len(posts)
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"TOTAL\t{total}")


if __name__ == "__main__":
    main()
