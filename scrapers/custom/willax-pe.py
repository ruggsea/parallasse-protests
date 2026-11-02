#!/usr/bin/env python3
"""Scrape willax.pe article URLs published 2026-09-25..2026-10-25.

Route: permissive robots.txt (feeds and search disallowed, sitemaps allowed)
-> WordPress REST API /wp-json/wp/v2/posts with after/before filters and
pagination (per_page=100).

Date: the article pages carry their publication date only in JSON-LD
datePublished / <meta article:published_time>, both in UTC (+00:00). The
REST field date_gmt is that exact UTC timestamp (verified identical to the
page JSON-LD for sample articles), so its date part is listed. The REST
'date' field is site-local (Peru, UTC-5) and differs by up to a day from
the page-stated UTC date near midnight; date_gmt matches the page exactly.

Yoast post-sitemaps were avoided: their <lastmod> is edit time, not
publish time. Feeds are disallowed by robots.txt.
"""
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = "2026-09-25"
END = "2026-10-25"
BASE = "https://willax.pe"
OUT = "data/urls_custom/willax-pe.tsv"

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def main():
    rows = {}  # url -> utc date
    page = 1
    while True:
        url = (
            f"{BASE}/wp-json/wp/v2/posts"
            f"?per_page=100&page={page}"
            f"&after=2026-09-24T00:00:00&before=2026-10-26T00:00:00"
            f"&_fields=date_gmt,link"
        )
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, retrying in 15s", flush=True)
            time.sleep(15)
            status, text, _ = fetch(url)
            if status != 200:
                print(f"page {page}: giving up (status {status})")
                break
        try:
            posts = json.loads(text)
        except Exception as e:
            print(f"page {page}: JSON error: {e}")
            break
        if not isinstance(posts, list):
            print(f"page {page}: unexpected payload {str(posts)[:200]}")
            break
        for p in posts:
            m = DATE_RE.match(p.get("date_gmt", ""))
            if not m:
                continue
            d = m.group(1)
            if d < START or d > END:
                continue
            link = (p.get("link") or "").strip()
            if link and link not in rows:
                rows[link] = d
        print(f"page {page}: {len(posts)} posts (total kept {len(rows)})", flush=True)
        if len(posts) < 100:
            break
        page += 1
        time.sleep(1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = defaultdict(int)
    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(rows):
            f.write(f"{link}\t{rows[link]}\n")
            per_day[rows[link]] += 1
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    days = sorted(per_day)
    if days:
        print(f"days covered: {len(days)} ({days[0]}..{days[-1]})")
    for d in days:
        print(f"  {d}: {per_day[d]}")
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"probe {probe}: {per_day.get(probe, 0)}")


if __name__ == "__main__":
    main()
