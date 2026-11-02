#!/usr/bin/env python3
"""Scrape article URLs published by palinfo.com between 2026-09-25 and 2026-10-25.

Route: robots.txt is permissive (Allow: /, only training bots disallowed) ->
WordPress REST API /wp-json/wp/v2/posts with _fields=link,date and
after/before local-time filters (1-day margin each side for the site's +03:00
timezone). Listed date = the YYYY/MM/DD in the article URL path
(/news/YYYY/MM/DD/<id>/), which equals the REST local date and the page
JSON-LD datePublished date-part (verified on samples).
"""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://palinfo.com"
AFTER = "2026-09-24T00:00:00"   # 1-day margin before window start
BEFORE = "2026-10-26T00:00:00"  # 1-day margin after window end
WIN_START = date(2026, 9, 25)
WIN_END = date(2026, 10, 25)

OUT = "data/urls_custom/palinfo-com.tsv"
DATE_RE = re.compile(r"/news/(\d{4})/(\d{2})/(\d{2})/\d+/")


def main():
    found = {}  # url -> date
    mismatches = 0
    page = 1
    while page <= 60:
        url = (f"{BASE}/wp-json/wp/v2/posts?_fields=link,date&per_page=100"
               f"&after={AFTER}&before={BEFORE}&page={page}")
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"page {page}: status {status}, stopping", file=sys.stderr)
            break
        rows = json.loads(text)
        if not rows:
            break
        for row in rows:
            link = row["link"]
            rest_date = date.fromisoformat(row["date"][:10])
            m = DATE_RE.search(link)
            if m:
                url_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                url_date = rest_date
            if url_date != rest_date:
                mismatches += 1
            if not (WIN_START <= url_date <= WIN_END):
                continue
            if link not in found:
                found[link] = url_date
        print(f"page {page}: {len(rows)} rows, total {len(found)}")
        if len(rows) < 100:
            break
        page += 1

    print(f"URL-date vs REST-date mismatches: {mismatches}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for link, d in sorted(found.items()):
            f.write(f"{link}\t{d.isoformat()}\n")

    per_day = {}
    for d in found.values():
        per_day[d] = per_day.get(d, 0) + 1
    for day in sorted(per_day):
        print(f"{day.isoformat()}: {per_day[day]}")
    print(f"TOTAL: {len(found)} unique URLs -> {OUT}")


if __name__ == "__main__":
    main()
