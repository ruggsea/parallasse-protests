#!/usr/bin/env python3
"""List 1tv.ru (Channel One Russia) article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26): robots.txt is permissive (200, only /free, /profile,
/search disallowed; Crawl-delay 1) and names no sitemaps, but https://www.1tv.ru/
sitemap.xml is a sitemapindex whose per-year news sitemaps are flat urlsets:
sitemap-news-2026.xml holds ~26k article URLs of the form
https://www.1tv.ru/news/YYYY-MM-DD/<id> with the publication date embedded in
the URL path. That path date is the date the site itself states: it matches the
date shown on the article page (e.g. /news/2026-09-30/554659 shows
"30 сентября 2026, 12:55"; /news/2026-10-20/556551 shows
"20 октября 2026, 09:09"). The <lastmod> is the edit time (a few minutes after
publish), so it is NOT used. One request covers the whole window; every day in
the window has 66-113 URLs (min 15 easily met).
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START, END = "2026-09-25", "2026-10-25"
SITEMAP = "https://www.1tv.ru/sitemap-news-2026.xml"
OUT = Path("data/urls_custom/1tv-ru.tsv")
URL_RE = re.compile(
    r"<loc>\s*(https://www\.1tv\.ru/news/(\d{4}-\d{2}-\d{2})/\d+)\s*</loc>"
)


def main():
    status, text, _ = fetch(SITEMAP)
    if status != 200 or not text:
        print(f"FAIL: sitemap fetch status={status}", file=sys.stderr)
        sys.exit(1)

    seen = {}
    for url, date in URL_RE.findall(text):
        if START <= date <= END and url not in seen:
            seen[url] = date

    if not seen:
        print("FAIL: no URLs found in window", file=sys.stderr)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(seen, key=lambda u: (seen[u], u)):
            f.write(f"{url}\t{seen[url]}\n")

    counts = Counter(seen.values())
    print(f"wrote {len(seen)} unique URLs to {OUT}")
    for day in sorted(counts):
        print(f"  {day}: {counts[day]}")
    expected = []
    for day in range(25, 31):
        expected.append(f"2026-09-{day:02d}")
    for day in range(1, 26):
        expected.append(f"2026-10-{day:02d}")
    missing = [d for d in expected if d not in counts]
    if missing:
        print(f"WARNING: days with no URLs: {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
