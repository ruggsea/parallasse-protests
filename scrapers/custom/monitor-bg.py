#!/usr/bin/env python3
"""Scrape monitor.bg article URLs for 2026-09-25..2026-10-25.

Route (verified): monitor.bg is a mirror domain of telegraph.bg (same Netinfo
platform; the monitor.bg homepage links to telegraph.bg, and identical bytes are
served for article paths on both domains). monitor.bg/robots.txt is permissive
and its sitemap index (monitor.bg/sitemap.xml == telegraph.bg/sitemap.xml)
lists /sitemap/latest_news plus one sitemap per top-level section. Those
sitemaps contain <loc> (telegraph.bg URL) + <lastmod>; for every article
checked, lastmod equals the page JSON-LD datePublished exactly (dateModified is
unset, e.g. 489231: 2026-04-20T21:13:00+03:00 in both). latest_news additionally
carries news:publication_date, which is preferred when present.
Each section sitemap holds ~1000 newest-first URLs reaching back to ~April 2026,
so the union of the 13 index sitemaps covers the whole window; extra guessed
section sitemaps (telegraphtv, pr, izbori) are tried and skipped on 404.
URLs are rewritten to the monitor.bg domain (task domain), deduped, and the
date written is the sitemap publication date (date part).
"""
import re
import sys
import os
from collections import defaultdict
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://telegraph.bg/sitemap"
SITEMAPS = [
    "/latest_news",
    "/category/bulgaria",
    "/category/sport",
    "/category/svetat",
    "/category/zdrave",
    "/category/krimi",
    "/category/biznes",
    "/category/gradat",
    "/category/obshtestvo",
    "/category/svetski",
    "/category/hi-tech",
    "/category/interesno",
    "/category/telegraphplus",
    "/category/zodiac",
    # guessed extras (sections present on the site but not in the index)
    "/category/telegraphtv",
    "/category/pr",
    "/category/izbori",
]

START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/monitor-bg.tsv"

URL_RE = re.compile(r"<url>\s*<loc>([^<]+)</loc>(.*?)</url>", re.S)
PUBDATE_RE = re.compile(r"<news:publication_date>([^<]+)</news:publication_date>")
LASTMOD_RE = re.compile(r"<lastmod>([^<]+)</lastmod>")


def is_article(loc: str) -> bool:
    # article URLs look like https://telegraph.bg/<section>/<sub>/<slug>-<id>
    if not loc.startswith("http"):
        return False
    path = loc.split("/", 3)
    if len(path) < 4:
        return False
    slug = path[3].strip("/")
    return bool(re.search(r"-\d{4,}$", slug))


def main() -> None:
    found = {}  # url -> date
    for path in SITEMAPS:
        url = BASE + path
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"skip {path}: status {status}", file=sys.stderr)
            continue
        n = 0
        for loc, block in URL_RE.findall(text):
            loc = loc.strip()
            if not is_article(loc):
                continue
            m = PUBDATE_RE.search(block) or LASTMOD_RE.search(block)
            if not m:
                continue
            d = m.group(1)[:10]
            if not (START <= d <= END):
                continue
            # canonical URL on the task domain (monitor.bg serves identical bytes)
            mu = "https://monitor.bg" + loc.split("/", 3)[3]
            if mu not in found:
                found[mu] = d
                n += 1
        print(f"{path}: +{n} in-window (total {len(found)})", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = defaultdict(int)
    with open(OUT, "w", encoding="utf-8") as f:
        for mu in sorted(found, key=lambda u: (found[u], u)):
            f.write(f"{mu}\t{found[mu]}\n")
            per_day[found[mu]] += 1
    print(f"wrote {len(found)} URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    missing = [d for d in (START, END) if not (START <= d <= END)]
    if not per_day:
        sys.exit("no URLs found")


if __name__ == "__main__":
    main()
