#!/usr/bin/env python3
"""Custom scraper: Kom Chad Luek (komchadluek.net), Thailand.

Route: robots.txt is permissive (disallows only /search, *.php, *.htm*) and points at
/sitemap_index.xml, which lists per-month sitemaps on media.komchadluek.net:
  https://media.komchadluek.net/sitemap/xml/2026/sitemap_2026_09.xml
  https://media.komchadluek.net/sitemap/xml/2026/sitemap_2026_10.xml
Each is a Google News sitemap: every <url> carries <news:publication_date> in
+07:00 (Bangkok time). Verified on a sample article (https://www.komchadluek.net/news/crime/624686):
the page's own embedded "article_publication_date" ("25 ต.ค. 2569 | 20:49 น.") equals the
sitemap's <news:publication_date> to the minute (2026-10-25T20:49:00+07:00), so the
date-part of publication_date (+07:00) is the publication date as the site states it.
Fallback: <lastmod> for entries without a news block.

Output: data/urls_custom/komchadluek-net.tsv  lines "URL<TAB>YYYY-MM-DD", unique,
window 2026-09-25 .. 2026-10-25 (inclusive, Bangkok local date).
"""
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/komchadluek-net.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MONTHS = [
    "https://media.komchadluek.net/sitemap/xml/2026/sitemap_2026_09.xml",
    "https://media.komchadluek.net/sitemap/xml/2026/sitemap_2026_10.xml",
]


def get(url, tries=3):
    for i in range(tries):
        st, body, _ = fetch(url)
        if st == 200 and body:
            return body
        print(f"retry {i + 1} {url} status={st}")
        time.sleep(5 * (i + 1))
    return None


def parse_sitemap(body):
    """Yield (url, local date) for each <url> in a Google News sitemap."""
    for m in re.finditer(r"<url>(.*?)</url>", body, re.S):
        block = m.group(1)
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
        if not loc:
            continue
        url = loc.group(1)
        pub = re.search(r"<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>", block)
        last = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
        stamp = (pub or last)
        if not stamp:
            continue
        d = stamp.group(1)[:10]
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        yield url, dd


def main():
    seen = {}
    for url in MONTHS:
        body = get(url)
        if body is None:
            print(f"FAIL {url}", file=sys.stderr)
            continue
        n = 0
        for u, dd in parse_sitemap(body):
            if START <= dd <= END:
                if u not in seen:
                    seen[u] = dd
                n += 1
        print(f"fetched {url}: {len(body)} bytes, {n} entries in window")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for u, dd in rows:
            f.write(f"{u}\t{dd.isoformat()}\n")
    print(f"wrote {len(rows)} unique urls to {OUT}")

    per_day = {}
    for _, dd in rows:
        per_day[dd] = per_day.get(dd, 0) + 1
    for d in sorted(per_day):
        print(d.isoformat(), per_day[d])
    for d in (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)):
        flag = "OK" if per_day.get(d, 0) >= 15 else "SHORT"
        print(f"target {d.isoformat()}: {per_day.get(d, 0)} {flag}")


if __name__ == "__main__":
    main()
