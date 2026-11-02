#!/usr/bin/env python3
"""List g4media.ro article URLs published 2026-09-25..2026-10-25.

Route: WordPress REST API /wp-json/wp/v2/posts (robots.txt permissive,
names sitemaps; the news sitemap only holds the newest ~500 URLs, so the
REST API is the only source covering the whole window).

We list 'date_gmt' (UTC), which is exactly what the article page states as
JSON-LD datePublished ("...T...+00:00") and matches the news sitemap's
publication_date.

Writes data/urls_custom/g4media-ro.tsv: URL<TAB>YYYY-MM-DD, unique URLs.
"""
import json
import os
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.g4media.ro"
API = BASE + "/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/g4media-ro.tsv"


def main():
    found = {}  # url -> date (UTC, YYYY-MM-DD, as stated on the page)
    page = 1
    stop = False
    while not stop and page <= 200:
        url = f"{API}?_fields=date,link,date_gmt&per_page=100&page={page}"
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, retrying once")
            status, text, _ = fetch(url)
            if status != 200:
                print(f"page {page}: failed with {status}, aborting pagination")
                break
        try:
            posts = json.loads(text)
        except Exception as e:
            print(f"page {page}: bad JSON: {e}")
            break
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            d = (p.get("date_gmt") or "")[:10]
            link = (p.get("link") or "").strip()
            if not link:
                continue
            host = urlparse(link).netloc.lower()
            if host not in ("www.g4media.ro", "g4media.ro"):
                continue  # sister-site cross-posts (e.g. economedia.ro)
            if d < START:
                stop = True
                continue
            if START <= d <= END and link not in found:
                found[link] = d
        oldest = min((p.get("date_gmt") or "")[:10] for p in posts if p.get("date_gmt"))
        print(f"page {page}: {len(posts)} posts, oldest {oldest}, total in window {len(found)}")
        if len(posts) < 100:
            break
        page += 1

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for link, d in rows:
            f.write(f"{link}\t{d}\n")
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    days = Counter(d for _, d in rows)
    for d in sorted(days):
        print(f"{d}\t{days[d]}")
    missing = [d for d in (START, "2026-09-30", "2026-10-10", "2026-10-20", END) if d not in days]
    if missing:
        print(f"WARNING: no URLs for {missing}")


if __name__ == "__main__":
    main()
