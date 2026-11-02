#!/usr/bin/env python3
"""List National Post article URLs published 2026-09-25..2026-10-25.

Route: nationalpost.com runs WordPress. /robots.txt (UA *) disallows only
/wp-admin/, /cms-admin/ and bare query disallows that never match (robots
matching strips query strings), and /wp-json is reachable (200, verified).
Use the WP REST API:
  /wp-json/wp/v2/posts?per_page=100&_fields=link,date&after=<start>&before=<end>&page=N
The REST "date" is the post_date column in site-local time (America/Toronto).
Verified: post date 2026-10-25T17:47:08 (REST) == page JSON-LD
datePublished 2026-10-25T21:47:08+0000 (UTC) -> same local calendar day.
Bounds are given with 1-day margin in local time; the date part is filtered
to the window afterwards, so the DST flip on 2026-10-25 cannot drop items.
Fallback route (if REST dies): /sitemap.xml (flat, ~7 days of edits) is not
enough; /sitemap-old.xml indexes per-day story sitemaps whose lastmod is edit
time, so it is only usable as a URL source, not a date source.
"""
import json
import re
import sys
import time
from collections import defaultdict
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://nationalpost.com/wp-json/wp/v2/posts"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
# 1-day margin, local time (WP compares against the local post_date column)
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T23:59:59"

def main():
    seen = {}  # url -> local date string
    page = 1
    total_posts = 0
    while True:
        url = f"{BASE}?per_page=100&_fields=link,date&after={AFTER}&before={BEFORE}&page={page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            # slow down and retry a couple of times, then stop
            for attempt in range(3):
                time.sleep(10 * (attempt + 1))
                status, text, _ = fetch(url)
                if status == 200 and text:
                    break
        if status != 200 or not text:
            print(f"page {page}: status {status}, stopping", file=sys.stderr)
            break
        try:
            rows = json.loads(text)
        except json.JSONDecodeError:
            print(f"page {page}: bad JSON, stopping", file=sys.stderr)
            break
        if not isinstance(rows, list) or not rows:
            break
        total_posts += len(rows)
        for row in rows:
            link = row.get("link") or ""
            d = (row.get("date") or "")[:10]
            if not link or not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                continue
            y, m, dd = map(int, d.split("-"))
            try:
                day = date(y, m, dd)
            except ValueError:
                continue
            if START <= day <= END:
                seen.setdefault(link, d)
        if len(rows) < 100:
            break
        page += 1

    per_day = defaultdict(int)
    out = "data/urls_custom/nationalpost-com.tsv"
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        for link in sorted(seen):
            f.write(f"{link}\t{seen[link]}\n")
            per_day[seen[link]] += 1
    print(f"REST posts fetched: {total_posts}")
    print(f"unique in-window URLs written: {len(seen)}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    if not per_day:
        sys.exit(1)

if __name__ == "__main__":
    main()
