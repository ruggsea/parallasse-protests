#!/usr/bin/env python3
"""List gandul.ro article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, permissive, names /sitemaps/index.xml and
/sitemaps/news-sitemap.xml) -> WordPress REST API.

The news sitemap holds only the ~177 newest items (back to 2026-10-24),
not the whole window. The numbered post sitemaps have scattered lastmods
and their entry lastmod is not reliably publication time. The WP REST API
(/wp-json/wp/v2/posts) is open and covers everything: we page with
per_page=100, local-time after/before bounds (1-day margin each side),
and keep the 'date' field (site-local Europe/Bucharest), which equals the
article page's JSON-LD datePublished exactly
(verified: REST date 2026-10-24T09:00:56 == page datePublished
2026-10-24T09:00:56+03:00 for post 21043364).

Writes data/urls_custom/gandul-ro.tsv: URL<TAB>YYYY-MM-DD, unique URLs.
"""
import json
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

API = "https://www.gandul.ro/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
# WP after/before filter on the local post_date column; 1-day margin each
# side so timezone edges cannot drop a day, then we filter the date part.
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T00:00:00"
OUT = "data/urls_custom/gandul-ro.tsv"


def main():
    found = {}  # url -> local date YYYY-MM-DD
    page = 1
    max_page = 400
    while page <= max_page:
        url = (f"{API}?_fields=date,link&per_page=100"
               f"&after={AFTER}&before={BEFORE}&page={page}")
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, retrying once")
            status, text, _ = fetch(url)
            if status != 200:
                print(f"page {page}: failed with {status}, aborting")
                break
        try:
            posts = json.loads(text)
        except Exception as e:
            print(f"page {page}: bad JSON: {e}")
            break
        if not isinstance(posts, list):
            print(f"page {page}: not a list, aborting")
            break
        if not posts:
            break
        for p in posts:
            d = (p.get("date") or "")[:10]
            link = (p.get("link") or "").strip()
            if not link or not d:
                continue
            host = urlparse(link).netloc.lower()
            if host not in ("gandul.ro", "www.gandul.ro"):
                continue
            if d < START or d > END:
                continue
            found[link] = d
        print(f"page {page}: {len(posts)} posts, total {len(found)}", flush=True)
        if len(posts) < 100:
            break
        page += 1

    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(found):
            f.write(f"{link}\t{found[link]}\n")

    counts = Counter(found.values())
    print(f"wrote {len(found)} urls to {OUT}")
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")
    missing = [d for d in
               (["2026-09-30", "2026-10-10", "2026-10-20"])
               if counts.get(d, 0) < 15]
    print("check-days short of 15:", missing or "none")


if __name__ == "__main__":
    main()
