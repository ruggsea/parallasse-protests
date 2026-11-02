#!/usr/bin/env python3
"""List Colombo Telegraph (colombotelegraph.com) article URLs for 2026-09-25..2026-10-25.

Route: WordPress REST API /wp-json/wp/v2/posts (robots.txt allows it; it disallows
only /wp-admin/). The REST 'date' field is the true publication time in the site's
local timezone (Sri Lanka, UTC+5:30, no DST). Verified on samples: REST local date
minus 5:30 == page JSON-LD datePublished to the second.

The Yoast post-sitemaps (index.php/post-sitemapN.xml) were tried first but their
<lastmod> is the post EDIT time (matches page JSON-LD dateModified exactly), not
publication time, so they were rejected as the date source.

Listed date = UTC date-part of the publication instant, i.e. exactly the date-part
of the page JSON-LD datePublished (+00:00). The check's re-fetch tolerance is 1 day;
UTC is the exact-match choice.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.colombotelegraph.com"
API = BASE + "/wp-json/wp/v2/posts"
WINDOW_START = datetime.date(2026, 9, 25)
WINDOW_END = datetime.date(2026, 10, 25)
LKT = datetime.timezone(datetime.timedelta(hours=5, minutes=30))  # Asia/Colombo, no DST
OUT = "data/urls_custom/colombotelegraph-com.tsv"

# One-day local-time margins on each side of the window so the UTC/local
# conversion at the edges cannot drop or admit a post.
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T23:59:59"


def to_utc_date(local_iso):
    """REST date is naive local LKT; return the UTC calendar date."""
    dt = datetime.datetime.fromisoformat(local_iso).replace(tzinfo=LKT)
    return dt.astimezone(datetime.timezone.utc).date()


def main():
    posts = []
    page = 1
    while True:
        url = f"{API}?per_page=100&_fields=date,link&page={page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            raise SystemExit(f"REST page {page} failed: HTTP {status}")
        batch = json.loads(text)
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 50:  # safety
            break

    seen = {}
    for p in posts:
        try:
            d = to_utc_date(p["date"])
        except (ValueError, KeyError):
            continue
        if WINDOW_START <= d <= WINDOW_END:
            u = p["link"].strip()
            if u not in seen:
                seen[u] = d

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    print("per-day counts:")
    for d in sorted(per_day):
        print(f"  {d.isoformat()}  {per_day[d]}")
    days_covered = sum(1 for d in per_day)
    total_days = (WINDOW_END - WINDOW_START).days + 1
    print(f"days with >=1 URL: {days_covered}/{total_days}")
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        n = per_day.get(datetime.date.fromisoformat(target), 0)
        print(f"TARGET {target}: {n} URLs")


if __name__ == "__main__":
    main()
