#!/usr/bin/env python3
"""List qudsn.ps (Quds News Network) article URLs published 2026-09-25..2026-10-25.

The qudsn.ps domain currently serves a static SPA shell (identical homepage HTML,
meta x-static-page) for every path, including /robots.txt, /sitemap.xml and
/post?id=... . Its own homepage links every article to https://qudsn.co/post?id=NNN&slug=...,
which is the outlet's live domain. qudsn.co/robots.txt (200) allows User-agent: *
(only /dashboard, /change-language, /login, /search, /search_page disallowed) and
advertises Sitemap: https://qudsn.co/sitemap.xml.

That sitemap is one flat urlset (4.9 MB, 10,000 posts, full history back to
2025-01-01) where <lastmod> is the post's local (+03:00) time. Verified on 4
samples across 09-30/10-10/10-20: lastmod matches the page's JSON-LD
dateModified exactly and datePublished within ~3 minutes, same calendar date.

So: fetch the one sitemap, keep /post URLs whose lastmod date falls in the
window, dedupe, and write URL<TAB>YYYY-MM-DD (lastmod date).
"""
import html
import os
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://qudsn.co"
SITEMAP = BASE + "/sitemap.xml"
WINDOW = ("2026-09-25", "2026-10-25")
OUT = "data/urls_custom/qudsn-ps.tsv"

PAIR = re.compile(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>")


def main():
    status, text, _ = fetch(SITEMAP)
    if status != 200 or not text:
        raise SystemExit(f"sitemap fetch failed: status {status}")

    seen = {}  # url -> date
    for raw_loc, lastmod in PAIR.findall(text):
        loc = html.unescape(raw_loc).strip()
        if "/post" not in loc:
            continue
        day = lastmod[:10]
        if WINDOW[0] <= day <= WINDOW[1]:
            seen.setdefault(loc, day)

    if not seen:
        raise SystemExit("no post URLs found in window; check sitemap format")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            f.write(f"{url}\t{seen[url]}\n")

    per_day = Counter(seen.values())
    print(f"wrote {len(seen)} unique URLs to {OUT}")
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]}")
    from datetime import date, timedelta
    d = date(2026, 9, 25)
    while d <= date(2026, 10, 25):
        iso = d.isoformat()
        if iso not in per_day:
            print(f"WARNING: no URLs for {iso}")
        d += timedelta(days=1)


if __name__ == "__main__":
    main()
