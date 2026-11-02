#!/usr/bin/env python3
"""Thai PBS (thaipbs.or.th) article URL list for 2026-09-25..2026-10-25.

Route: robots.txt (permissive, names /sitemap.xml) -> sitemap index ->
/sitemap/sitemap_news_monthly.xml is STALE (newest entry 2024-12), so the
month files are derived from the window instead:
  https://www.thaipbs.or.th/sitemap/sitemap-news/news-YYYY-MM.xml
Each month file is a flat urlset, newest-first, with <lastmod> that IS the
publication time (+07:00, Thai local) -- verified == page JSON-LD
datePublished to the second (e.g. /news/content/571387: 2026-10-20T20:36:03+07:00
in both), and == news:publication_date in /sitemap/sitemap_news.xml.
Listed date = date part of lastmod (site's own time zone).
"""
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/thaipbs-or-th.tsv"
WINDOW_START = date(2026, 9, 25)
WINDOW_END = date(2026, 10, 25)

MONTHS = ["2026-09", "2026-10"]  # months intersecting the window

ENTRY = re.compile(
    r"<loc>\s*(?P<loc>[^<]+?)\s*</loc>\s*<lastmod>\s*(?P<lastmod>[^<]+?)\s*</lastmod>",
    re.S,
)
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def lastmod_date(lm: str):
    m = DATE_RE.match(lm)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def main() -> int:
    seen = {}  # url -> date
    for month in MONTHS:
        url = f"https://www.thaipbs.or.th/sitemap/sitemap-news/news-{month}.xml"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"FAIL {url} status={status}", file=sys.stderr)
            return 1
        n = 0
        for m in ENTRY.finditer(text):
            d = lastmod_date(m.group("lastmod"))
            if d is None or not (WINDOW_START <= d <= WINDOW_END):
                continue
            loc = m.group("loc").strip()
            if loc in seen:
                continue
            seen[loc] = d
            n += 1
        print(f"fetched {url}: {n} new in-window URLs")

    # sanity: expected per-day coverage
    days = Counter(d for d in seen.values())
    for target in (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)):
        print(f"  {target.isoformat()}: {days.get(target, 0)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for loc, d in sorted(seen.items()):
            f.write(f"{loc}\t{d.isoformat()}\n")

    total = len(seen)
    ndays = len(days)
    print(f"wrote {total} URLs across {ndays} days to {OUT}")
    if ndays == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
