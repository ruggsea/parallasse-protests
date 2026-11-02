#!/usr/bin/env python3
"""Vreme (Serbia, vreme.com) URL lister, 2026-09-25 .. 2026-10-25.

Route: permissive robots.txt (Allow: /) -> WordPress REST API
https://vreme.com/wp-json/wp/v2/posts?per_page=100&page=N (newest first).
The REST field 'date' is the Belgrade-local publication time and matches the
page JSON-LD datePublished to the second (verified: 2026-10-26T07:49:10 on
both). We list the date part of 'date'. Yoast post-sitemap lastmod is edit
time, so the sitemap is not used for dates.
"""
import sys
import json
import collections
import os
import datetime as dt

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = "2026-09-25"
END = "2026-10-25"
BASE = "https://vreme.com/wp-json/wp/v2/posts"
OUT = "data/urls_custom/vreme-com.tsv"

def main():
    found = {}  # url -> date
    page = 1
    stop = False
    while not stop:
        url = f"{BASE}?per_page=100&_fields=date,link&page={page}"
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, stopping", file=sys.stderr)
            break
        try:
            arr = json.loads(text)
        except Exception as e:
            print(f"page {page}: bad json: {e}", file=sys.stderr)
            break
        if not isinstance(arr, list) or not arr:
            break
        for p in arr:
            d = p.get("date", "")[:10]
            link = p.get("link", "").rstrip("/")
            if not link or d < START or d > END:
                if d and d < START:
                    stop = True  # newest-first: everything older is out of window
                continue
            found[link] = d
        print(f"page {page}: {len(arr)} posts, newest {arr[0]['date'][:10]}", file=sys.stderr)
        page += 1
        if page > 40:
            print("safety stop at 40 pages", file=sys.stderr)
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per = collections.Counter()
    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(found, key=lambda u: (found[u], u)):
            f.write(f"{link}\t{found[link]}\n")
            per[found[link]] += 1
    print(f"wrote {len(found)} urls to {OUT}")
    for d in sorted(per):
        print(f"{d}: {per[d]}")
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {d}: {per.get(d, 0)} urls")

if __name__ == "__main__":
    main()
