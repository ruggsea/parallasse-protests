#!/usr/bin/env python3
"""Scrape La Silla Vacía (lasillavacia.com) article URLs for 2026-09-25..2026-10-25.

Route (WordPress, robots.txt disallows /wp-json/ so REST is closed):
  daily date archives https://www.lasillavacia.com/YYYY/MM/DD/ (paged: /page/N/)
  - each <article class="... type-post ..."> block = one post; first internal href = article URL
  - listed date = the archive day (site-stated). Verified: every card's first <time>
    (publication datetime, -05:00) carries the archive day; article pages expose the
    same day via <meta article:published_time> and JSON-LD NewsArticle.datePublished.
  - /wp-sitemap.xml (Yoast) exists but post permalinks have no date in the path and
    lastmod is edit time, so the archives are the reliable per-day route.
"""
import datetime as dt
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.lasillavacia.com"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
MAX_PAGES = 10

SKIP_PREFIXES = (
    "https://www.lasillavacia.com/author/",
    "https://www.lasillavacia.com/category/",
    "https://www.lasillavacia.com/tag/",
    "https://www.lasillavacia.com/feed",
    "https://www.lasillavacia.com/wp-",
    "https://www.lasillavacia.com/comments/",
    "https://www.lasillavacia.com/especiales/",
)


def article_urls(page_html):
    urls = []
    for m in re.finditer(
        r'<article\b[^>]*class="[^"]*type-post[^"]*"[^>]*>(.*?)(?=<article\b|</main>)',
        page_html,
        re.S,
    ):
        block = m.group(1)
        hrefs = re.findall(r'href="(https://www\.lasillavacia\.com/[^"]+?/)"', block)
        for h in hrefs:
            if "/page/" in h:
                continue
            if any(h.startswith(p) or h.rstrip("/") == BASE.rstrip("/") for p in SKIP_PREFIXES):
                continue
            urls.append(h)
            break
    return urls


def main():
    rows = {}  # url -> date
    per_day = {}
    day = START
    while day <= END:
        dstr = day.isoformat()
        urls = []
        for n in range(1, MAX_PAGES + 1):
            path = f"{dstr}/" if n == 1 else f"{dstr}/page/{n}/"
            status, text, _ = fetch(BASE + "/" + path)
            if status != 200 or not text:
                break
            found = article_urls(text)
            if not found:
                break
            urls.extend(found)
            if len(found) < 10:  # last partial page
                break
        per_day[dstr] = len(set(urls))
        for u in urls:
            if u not in rows:
                rows[u] = dstr
        day += dt.timedelta(days=1)

    out = "data/urls_custom/lasillavacia-com.tsv"
    with open(out, "w") as f:
        for u, d in sorted(rows.items()):
            f.write(f"{u}\t{d}\n")

    total = len(rows)
    print(f"wrote {total} URLs to {out}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")


if __name__ == "__main__":
    main()
