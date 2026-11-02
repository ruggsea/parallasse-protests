#!/usr/bin/env python3
"""Scrape article URLs + publish dates for Alfa TV news (vesti.alfa.mk), window 2026-09-25..2026-10-25.

Route:
- alfa.mk main site: WordPress, robots permissive, sitemap https://alfa.mk/wp-sitemap.xml.
  Its posts sitemap (wp-sitemap-posts-post-1.xml, 778 URLs) is STALE: newest lastmod 2026-08-04.
- Actual news lives on the subdomain vesti.alfa.mk (links on the alfa.mk homepage).
  robots permissive (only /wp/wp-admin/ disallowed), sitemap index https://vesti.alfa.mk/sitemap.xml
  lists 25 post sitemaps (~25k posts). wp-sitemap-posts-post-24.xml spans 2026-09-21..2026-10-15,
  wp-sitemap-posts-post-25.xml spans 2026-10-15..2026-10-26 -> the two files cover the window.
- Listed date = WP REST local 'date' (publish time, site timezone Europe/Skopje),
  not <lastmod> (edit time; 'modified' differs on edited posts).
  WP REST /wp-json/wp/v2/posts supports after/before (local time) and is robots-allowed.
  Europe/Skopje falls back CEST->CET on 2026-10-25, so local 'date' is used consistently
  throughout the window (matches what the pages display).

Writes data/urls_custom/alfa-mk.tsv: URL<TAB>YYYY-MM-DD, unique, no header.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/alfa-mk.tsv")
BASE = "https://vesti.alfa.mk/wp-json/wp/v2/posts"
AFTER = "2026-09-24T23:00:00"   # local (Europe/Skopje); we keep only >= 2026-09-25
BEFORE = "2026-10-26T01:00:00"  # local; we keep only <= 2026-10-25
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"
PER_PAGE = 100


def main():
    found = {}
    page = 1
    total = 0
    while True:
        url = f"{BASE}?per_page={PER_PAGE}&after={AFTER}&before={BEFORE}&page={page}&_fields=date,link"
        status, text, _ = fetch(url)
        total += 1
        if status != 200 or not text:
            print(f"page {page}: HTTP {status}, stopping", flush=True)
            break
        try:
            items = json.loads(text)
        except ValueError as e:
            print(f"page {page}: bad JSON ({e}), stopping", flush=True)
            break
        if not isinstance(items, list) or not items:
            print(f"page {page}: empty, stopping", flush=True)
            break
        stop = False
        for it in items:
            d = it.get("date", "")[:10]
            link = it.get("link", "").strip()
            if not d or not link.startswith("http"):
                continue
            if d < WIN_START:
                stop = True  # ordered newest-first; rest of window is gone
                continue
            if d > WIN_END:
                continue
            found[link] = d
        print(f"page {page}: {len(items)} posts, newest {items[0]['date'][:10]}, running total in-window {len(found)}", flush=True)
        if stop or len(items) < PER_PAGE:
            break
        page += 1
        if page > 60:  # hard safety cap on requests
            print("page cap 60 reached", flush=True)
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(found):
            f.write(f"{link}\t{found[link]}\n")

    days = {}
    for d in found.values():
        days[d] = days.get(d, 0) + 1
    print(f"requests used: {total}")
    print(f"unique URLs written: {len(found)} -> {OUT}")
    print("per-day counts:")
    for d in sorted(days):
        print(f"  {d}\t{days[d]}")
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {probe}: {days.get(probe, 0)} urls (need >= 15)")


if __name__ == "__main__":
    main()
