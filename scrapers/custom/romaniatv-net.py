#!/usr/bin/env python3
"""Scraper for romaniatv.net (România TV), window 2026-09-25 .. 2026-10-25.

Route: permissive robots.txt (disallows only /wp-admin/*, /poze/*, /*?s=) ->
WordPress REST API /wp-json/wp/v2/posts with after/before (site-local time)
and per_page=100 pagination. The REST 'date' field is the publication
datetime in the site's local time (EET/EEST; clocks fall back 2026-10-25),
which matches the article page's JSON-LD datePublished. Listed date = date
part of that local timestamp.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.romaniatv.net/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/romaniatv-net.tsv"


def main():
    seen = {}
    page = 1
    while True:
        url = (f"{BASE}?per_page=100&_fields=date,link"
               f"&after={START}T00:00:00&before={END}T23:59:59&page={page}")
        status, text, _ = fetch(url)
        if status == 400:
            break  # past the last page
        if status != 200 or not text:
            raise SystemExit(f"REST failed page {page}: HTTP {status}")
        items = json.loads(text)
        if not items:
            break
        for it in items:
            d = it["date"][:10]
            u = it["link"]
            if START <= d <= END and u not in seen:
                seen[u] = d
        # safety stop
        if page > 200 or len(items) < 100:
            break
        page += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u in sorted(seen):
            f.write(f"{u}\t{seen[u]}\n")
    per_day = Counter(seen.values())
    print(f"wrote {len(seen)} unique URLs to {OUT}")
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]}")


if __name__ == "__main__":
    main()
