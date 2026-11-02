#!/usr/bin/env python3
"""Caretas (caretas.pe, Peru) article-URL lister for 2026-09-25..2026-10-25.

Route: robots.txt (200, Yoast block, Disallow: empty = permissive, declares
https://caretas.pe/sitemap_index.xml) -> WP REST API /wp-json/wp/v2/posts
(after=2026-09-25T00:00:00&before=2026-10-26T00:00:00, per_page=100, paged),
which the site itself runs on WordPress. The REST 'date' field is the
site-local (America/Lima, -05:00) publication time; the article pages carry
the same instant as JSON-LD "datePublished" with -05:00 (verified: REST date
2026-10-25T22:06:37 == page datePublished 2026-10-25T22:06:37-05:00; the
page's other, +00:00 occurrence is the same instant in UTC).

Why not the sitemaps: the 37 Yoast post-sitemaps only carry <lastmod>, which
is EDIT time (post-sitemap37.xml holds 551 URLs from 2026-10-10..10-26 by
lastmod but also re-edited older posts), and the URLs have no date in the
slug, so a sitemap alone cannot assign publication dates. The REST API gives
the true publish time in a few requests.

Date listed = the REST 'date' day (site-local). trafilatura reads the +00:00
JSON-LD occurrence, i.e. the same instant in UTC, which is 0 or 1 day later
than site-local (Lima is UTC-5) - always within 1 day, and keeping the
site-local day keeps every listed date inside the window (a UTC day would
push posts published after 19:00 local on 2026-10-25 to 2026-10-26, outside).

Writes data/urls_custom/caretas-pe.tsv: URL<TAB>YYYY-MM-DD, unique, no header.
"""
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from polite_fetch import fetch  # noqa: E402

WINDOW_START = "2026-09-25"
WINDOW_END = "2026-10-25"
BASE = "https://caretas.pe/wp-json/wp/v2/posts"
PAGES_CAP = 60  # 6000 posts; the window has ~1000


def fetch_with_retry(url, tries=5, wait=10):
    status, text, _ = (None, None, None)
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return status, text
        print(f"  retry {i + 1} for {url}: status {status}", file=sys.stderr)
        time.sleep(wait * (i + 1))
    return status, (text or "")


def main():
    entries = {}
    page = 1
    while page <= PAGES_CAP:
        url = (f"{BASE}?after={WINDOW_START}T00:00:00"
               f"&before=2026-10-26T00:00:00&per_page=100&page={page}")
        status, text = fetch_with_retry(url)
        if status != 200 or not text:
            print(f"ERROR: REST fetch failed at page {page}, status {status}",
                  file=sys.stderr)
            sys.exit(1)
        try:
            posts = json.loads(text)
        except ValueError as e:
            print(f"ERROR: bad JSON at page {page}: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            link = p.get("link", "").strip()
            day = (p.get("date") or "")[:10]
            if not link or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                continue
            if not (WINDOW_START <= day <= WINDOW_END):
                continue
            link = link.rstrip("/") + "/"
            if link not in entries:
                entries[link] = day
        print(f"page {page}: {len(posts)} posts, total so far {len(entries)}",
              file=sys.stderr)
        if len(posts) < 100:
            break
        page += 1

    out = os.path.join(".", "data",
                       "urls_custom", "caretas-pe.tsv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for link in sorted(entries):
            f.write(f"{link}\t{entries[link]}\n")

    per_day = Counter(entries.values())
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")
    print(f"TOTAL\t{len(entries)}\t->\t{out}")

    missing = [d for d in ("2026-09-30", "2026-10-10", "2026-10-20")
               if per_day.get(d, 0) < 15]
    if missing:
        print(f"WARNING: fewer than 15 URLs on {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
