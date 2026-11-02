#!/usr/bin/env python3
"""List seoul.co.kr article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt (permissive: only /SpecialEdition/dev/, /xml/, /members/ disallowed)
declares /sitemap/sitemap_dailyArticle, a sitemapindex of monthly files
/sitemap/sitemap_dailyArticle_YYYYMMDD. Each file is a flat urlset of
https://www.seoul.co.kr/news/<section>.../YYYY/MM/DD/<article-id> with the
publication date in the URL path (== <lastmod> date, == page JSON-LD
datePublished to the day; KST). Two requests cover the whole window.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/seoul-co-kr.tsv"
START, END = "2026-09-25", "2026-10-25"

MONTHS = [
    "https://www.seoul.co.kr/sitemap/sitemap_dailyArticle_20260009",
    "https://www.seoul.co.kr/sitemap/sitemap_dailyArticle_20260010",
]

URL_RE = re.compile(
    r"<loc>\s*(https://www\.seoul\.co\.kr/news/[^<]*?/(\d{4})/(\d{2})/(\d{2})/\d+)</loc>"
)


def main():
    found = {}
    for url in MONTHS:
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"WARN: {url} -> status {status}", file=sys.stderr)
            continue
        for m in URL_RE.finditer(text):
            u, y, mo, d = m.group(1), m.group(2), m.group(3), m.group(4)
            date = f"{y}-{mo}-{d}"
            if START <= date <= END:
                found.setdefault(u, date)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    per_day = Counter()
    with OUT.open("w", encoding="utf-8") as f:
        for u in sorted(found):
            f.write(f"{u}\t{found[u]}\n")
            per_day[found[u]] += 1
            n += 1
    print(f"wrote {n} URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {d}: {per_day.get(d, 0)}")
    missing = [d for d in per_day if per_day[d] < 15]
    if missing:
        print("DAYS UNDER 15: " + ", ".join(f"{d}={per_day[d]}" for d in missing))


if __name__ == "__main__":
    main()
