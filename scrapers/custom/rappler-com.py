#!/usr/bin/env python3
"""List rappler.com article URLs published 2026-09-25 .. 2026-10-25.

Route: WP REST API /wp-json/wp/v2/posts with site-local date filters.
- robots.txt allows /wp-json/wp/v2/ (only /wp-json/rappler/ is disallowed).
- Yoast sitemaps do not cover recent articles: post-sitemap.xml holds 2001-2006
  posts; news-sitemap.xml holds only ~11 newest items; /latest/ pagination
  shows only 10 articles per page (~300 pages for the window).
- REST 'date' is site-local (PHT, UTC+8) and matches the date shown on the
  article page (<time datetime="...+08:00">) exactly; JSON-LD datePublished
  carries the same instant in UTC, so PHT date is within 1 day of either.
Writes data/urls_custom/rappler-com.tsv: URL<TAB>YYYY-MM-DD, unique, no header.
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.rappler.com/wp-json/wp/v2/posts"
START, END = "2026-09-25", "2026-10-25"
# generous REST bounds (site-local PHT); exact window enforced below by date string
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T23:59:59"
OUT = "data/urls_custom/rappler-com.tsv"
MAX_PAGES = 80

d0 = date.fromisoformat(START)
d1 = date.fromisoformat(END)


def main():
    posts = {}  # url -> date str (first wins)
    total = 0
    page = 1
    while page <= MAX_PAGES:
        url = (f"{BASE}?after={AFTER}&before={BEFORE}"
               f"&per_page=100&page={page}&_fields=date,link")
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: HTTP {status}, stopping", file=sys.stderr)
            break
        items = json.loads(text or "[]")
        total += len(items)
        if not items:
            break
        for it in items:
            d = (it.get("date") or "")[:10]
            u = (it.get("link") or "").strip()
            if not u or not re.match(r"^https?://", u) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                continue
            if not u in posts:
                posts[u] = d
        if len(items) < 100:
            break
        page += 1

    rows = []
    per_day = Counter()
    dropped = 0
    for u, d in sorted(posts.items(), key=lambda kv: (kv[1], kv[0])):
        dd = date.fromisoformat(d)
        if d0 <= dd <= d1:
            rows.append((u, d))
            per_day[d] += 1
        else:
            dropped += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")

    print(f"pages fetched: {page}, REST items: {total}, "
          f"in-window: {len(rows)}, out-of-window: {dropped}")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    thin = {d: n for d, n in per_day.items() if n < 15}
    print("days with <15 urls:", thin or "none")


if __name__ == "__main__":
    main()
