#!/usr/bin/env python3
"""List tvpublica.com.ar (Canal 7) article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
- https://www.tvpublica.com.ar is a Next.js SPA; unknown paths (incl. /feed,
  /sitemap.xml) return the homepage shell, so no sitemap/RSS is served there.
- The homepage __NEXT_DATA__ reveals the WordPress backend behind it:
  https://d3b5jqy5xuub7g.cloudfront.net (guid fields point there).
- That origin serves the standard WP REST API. posts are fetched from
  /wp-json/wp/v2/posts with after/before bounds (1-day margin) and pagination.
- REST field `date` is LOCAL (Buenos Aires, UTC-3) and equals the article
  page JSON-LD datePublished exactly (verified on multiple posts).
- Article pages on the outlet domain are https://www.tvpublica.com.ar/post/<slug>
  (server-rendered, 1500+ chars of text, carry datePublished).
"""
import json
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

REST_BASE = "https://d3b5jqy5xuub7g.cloudfront.net/wp-json/wp/v2/posts"
WWW_POST = "https://www.tvpublica.com.ar/post/"
WINDOW_START = date(2026, 9, 25)
WINDOW_END = date(2026, 10, 25)
# 1-day margin so WP's local-date filter cannot clip boundary days
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T23:59:59"
OUT = "data/urls_custom/tvpublica-com-ar.tsv"


def parse_day(s):
    y, m, d = s[:10].split("-")
    return date(int(y), int(m), int(d))


def main():
    seen = {}  # url -> date str (first wins; a slug maps to one post)
    page = 1
    while page <= 30:
        url = (f"{REST_BASE}?_fields=date,slug&per_page=100"
               f"&after={AFTER}&before={BEFORE}&page={page}")
        status, text, _ = fetch(url)
        if status != 200:
            raise SystemExit(f"REST API page {page} returned status {status}")
        data = json.loads(text)
        if not data:
            break
        for row in data:
            d = parse_day(row["date"])
            if WINDOW_START <= d <= WINDOW_END:
                u = WWW_POST + row["slug"]
                seen.setdefault(u, d.isoformat())
        if len(data) < 100:
            break
        page += 1

    per_day = Counter(seen.values())
    with open(OUT, "w", encoding="utf-8") as f:
        for u in sorted(seen):
            f.write(f"{u}\t{seen[u]}\n")

    print(f"wrote {len(seen)} URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")


if __name__ == "__main__":
    main()
