#!/usr/bin/env python3
"""Scrape The Walrus (thewalrus.ca) article URLs for 2026-09-25..2026-10-25.

Route: permissive robots.txt -> WP REST API /wp-json/wp/v2/posts.
Listed date = the REST 'date' field (the post's local Eastern Time date, the
same date the article page shows). date_gmt is UTC and can differ by hours,
so the local 'date' is used.
"""
import json
import os
import sys
import re

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://thewalrus.ca"
AFTER = "2026-09-25T00:00:00"
BEFORE = "2026-10-25T23:59:59"
OUT = "data/urls_custom/thewalrus-ca.tsv"


def main():
    seen = {}  # url -> date
    page = 1
    while True:
        url = (
            f"{BASE}/wp-json/wp/v2/posts"
            f"?per_page=100&_fields=date,link"
            f"&after={AFTER}&before={BEFORE}&page={page}"
        )
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, retrying once", file=sys.stderr)
            status, text, _ = fetch(url)
            if status != 200:
                print(f"page {page}: giving up after retry (status {status})", file=sys.stderr)
                break
        try:
            items = json.loads(text)
        except ValueError:
            print(f"page {page}: bad JSON, stopping", file=sys.stderr)
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            link = (it.get("link") or "").split("?")[0].split("#")[0]
            if not link:
                continue
            m = re.match(r"^(\d{4}-\d{2}-\d{2})T", it.get("date") or "")
            if not m:
                continue
            seen.setdefault(link, m.group(1))
        print(f"page {page}: {len(items)} items (total {len(seen)})", file=sys.stderr)
        if len(items) < 100:
            break
        page += 1
        if page > 40:
            print("safety stop at 40 pages", file=sys.stderr)
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(seen):
            d = seen[link]
            f.write(f"{link}\t{d}\n")
            per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    print(f"TOTAL: {len(seen)} unique URLs, {len(per_day)} days")


if __name__ == "__main__":
    main()
