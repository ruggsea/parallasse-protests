#!/usr/bin/env python3
"""Scrape pbc.ps (Palestinian Broadcasting Corporation) article URLs for 2026-09-25..2026-10-25.

Route: robots.txt (200, Allow: /) -> WordPress REST API /wp-json/wp/v2/posts
paginated with after/before filters. The REST `date` field is the post's
publication date in the site's local time (verified against article-page
JSON-LD datePublished: same instant, same calendar date). Yoast
post-sitemaps were checked but their <lastmod> is edit time, so the REST
date is the reliable one.

Output: data/urls_custom/pbc-ps.tsv  (URL<TAB>YYYY-MM-DD, unique, no header)
"""
import json
import sys
import time
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

OUT = "data/urls_custom/pbc-ps.tsv"
WINDOW_START = "2026-09-24T23:59:59"
WINDOW_END = "2026-10-26T00:00:00"
BASE = "https://www.pbc.ps/wp-json/wp/v2/posts?per_page=100&after=%s&before=%s&page=%d"


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
            if status == 200 and text:
                return status, text
            last = status
        except Exception as e:  # noqa: BLE001
            last = f"exc:{e}"
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed after {tries} tries: {url} (last={last})")


def main():
    seen = {}
    page = 1
    while page <= 30:
        status, text = get(BASE % (WINDOW_START, WINDOW_END, page))
        posts = json.loads(text)
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            url = (p.get("link") or "").strip()
            date = (p.get("date") or "")[:10]
            if not url.startswith("http") or len(date) != 10:
                continue
            # datePublished on the page is the same instant; the REST date is
            # in site-local time and matches the page's displayed date.
            if date not in ("", None):
                seen.setdefault(url, date)
        if len(posts) < 100:
            break
        page += 1

    with open(OUT, "w", encoding="utf-8") as f:
        for url, date in sorted(seen.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{url}\t{date}\n")

    per_day = Counter(seen.values())
    print(f"wrote {len(seen)} unique URLs across {len(per_day)} days -> {OUT}")
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]}")


if __name__ == "__main__":
    main()
