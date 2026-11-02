#!/usr/bin/env python3
"""List ellibero.cl article URLs published 2026-09-25..2026-10-25 (Santiago local).

Route: permissive robots (Yoast block, only /wp-admin/ etc. disallowed) ->
WP REST /wp-json/wp/v2/posts with after/before on the local post_date column.
REST 'date' field is Santiago local time and matches page JSON-LD datePublished
exactly (verified: post date 2026-10-26T04:55:00 local == page
datePublished 2026-10-26T07:55:00+00:00 == <time datetime='2026-10-26T04:55:00-03:00'>).
Yoast post-sitemap <lastmod> is edit time (May-dated legal notices carry June
lastmods), so it is not used.
"""
import datetime as dt
import json
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

OUT = "data/urls_custom/ellibero-cl.tsv"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
BASE = "https://ellibero.cl/wp-json/wp/v2/posts?per_page=100&_fields=date,link"
# Margin around the window; exact bounds enforced by date-part filter below.
PARAMS = f"&after=2026-09-24T00:00:00&before=2026-10-27T00:00:00"


def get(url, tries=4):
    last = None
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return status, text
        last = status
        if status in (429, 500, 502, 503, 504) or status is None:
            time.sleep(10 * (i + 1))
    return last, None


def main():
    items = {}  # url -> date part
    page = 1
    total_reqs = 0
    while True:
        url = f"{BASE}{PARAMS}&page={page}"
        status, text = get(url)
        total_reqs += 1
        if status != 200 or not text:
            print(f"ERROR page {page}: status {status}")
            break
        batch = json.loads(text)
        if not batch:
            break
        for it in batch:
            d = it["date"][:10]
            day = dt.date.fromisoformat(d)
            if START <= day <= END:
                items.setdefault(it["link"], d)
        if len(batch) < 100:
            break
        page += 1
        if page > 40:  # safety
            break

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(items.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as f:
        for link, d in rows:
            f.write(f"{link}\t{d}\n")

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"requests={total_reqs} urls={len(rows)} days={len(per_day)}")
    for d in sorted(per_day):
        print(d, per_day[d])
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"check {probe}: {per_day.get(probe, 0)}")


if __name__ == "__main__":
    main()
