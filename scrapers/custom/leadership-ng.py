#!/usr/bin/env python3
"""List leadership.ng (Leadership, Nigeria) article URLs for 2026-09-25..2026-10-25.

Route: WordPress REST API. robots.txt (200, only disallows /wp-admin/) names
https://leadership.ng/sitemap_index.xml, but that index is stale: its newest
lastmod is 2026-09-24T22:37Z, i.e. the whole sitemap set predates the window,
so it cannot cover it. The REST endpoint /wp-json/wp/v2/posts is open and
returns the local 'date' field (site timezone UTC+1, Nigeria) which matches the
article page JSON-LD datePublished to the second (verified on
/i-wrote-my-will-at-30-realised-i-didnt-want-children-despite-being-an-only-child-chude-jideonwo/,
page shows 2026-10-20T01:58:28+01:00).

after/before are compared in UTC (date_gmt), so we query with a 1-day margin
each side and filter client-side on the local date part.
"""
import json
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://leadership.ng/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
# 1-day margins (compared against UTC date_gmt; local = UTC+1)
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T23:59:59"
OUT = "data/urls_custom/leadership-ng.tsv"


def get(url, tries=10):
    """fetch() with retries: the site drops some TCP connections (status 0)."""
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return text
        if status == 429:
            time.sleep(30)
            continue
        if status in (0, 500, 502, 503, 504):
            time.sleep(3 + i)
            continue
        # other HTTP errors (4xx): not retryable
        return None
    return None


def main():
    found = {}  # url -> local date part
    page = 1
    requests = 0
    while True:
        url = (
            f"{BASE}?_fields=date,link&per_page=100&orderby=date&order=asc"
            f"&after={AFTER}&before={BEFORE}&page={page}"
        )
        t = get(url)
        requests += 1
        if t is None:
            print(f"page {page}: FAILED after retries", file=sys.stderr)
            break
        try:
            posts = json.loads(t)
        except ValueError:
            print(f"page {page}: unparseable JSON", file=sys.stderr)
            break
        if not isinstance(posts, list) or not posts:
            break
        beyond = False
        for p in posts:
            d = p.get("date", "")[:10]
            link = p.get("link", "")
            if not d or not link:
                continue
            if d > END:
                beyond = True
                continue
            if d >= START and d <= END:
                found.setdefault(link, d)
        if beyond or len(posts) < 100:
            break
        page += 1
        if page > 500:  # safety
            break

    # write TSV, sorted by date then URL
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for link, d in rows:
            f.write(f"{link}\t{d}\n")

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} urls to {OUT} (requests: {requests})")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    missing = [d for d in (START, END) if d not in per_day]
    for d in missing:
        print(f"MISSING DAY: {d}")
    # explicit check days
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"check-day {d}: {per_day.get(d, 0)} urls")


if __name__ == "__main__":
    main()
