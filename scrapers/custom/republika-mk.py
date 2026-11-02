#!/usr/bin/env python3
"""Republika (North Macedonia), republika.mk - custom URL scraper.

Window: 2026-09-25 .. 2026-10-25.
Output: data/urls_custom/republika-mk.tsv (URL<TAB>YYYY-MM-DD, unique, no header)

Route (probed 2026-10-26/27):
  robots.txt permissive (Yoast, empty Disallow) -> WordPress REST
  /wp-json/wp/v2/posts?per_page=100&_fields=date,date_gmt,link,content
  walked with a one-day buffer around the window: 28 requests for the window.

  Listed date = date-part of date_gmt (UTC). The article page states the same
  instant (JSON-LD datePublished +00:00, trafilatura meta date), so the date is
  the one the page itself gives. Local 'date' is Skopje time (+02, +01 after
  2026-10-25 DST end) and can land on the previous day.

  Body length comes from the same response: content.rendered stripped of tags.
  Checked against trafilatura on the article pages, the two agree almost
  exactly (971 vs 965, 1336 vs 1336, 872 vs 872 chars), so a post is kept only
  when its article body is >= MIN_BODY chars. That drops photo-of-the-day
  galleries, lottery/bilbord ads, video stubs and one-paragraph briefs, which
  carry too little text to be an article. No per-article fetch is needed, so
  the whole run is ~28 requests and about a minute.
Counts at MIN_BODY=1650: 1141 urls, 31/31 days, 09-30=44, 10-10=16, 10-20=38.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data" / "urls_custom" / "republika-mk.tsv"
BASE = "https://republika.mk"
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"
REST_AFTER = "2026-09-24T00:00:00"   # one-day buffer, filter runs on local date
REST_BEFORE = "2026-10-26T23:59:59"
MIN_BODY = 1650                      # article body chars; trafilatura on page == this
PER_PAGE = 100
MAX_PAGES = 80
TAGS = re.compile(r"<[^>]+>")


def plain_len(rendered):
    return len(re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", rendered or ""))).strip())


def walk():
    """Return {url: 'YYYY-MM-DD'} for in-window posts with a real article body."""
    found = {}
    posts = 0
    for page in range(1, MAX_PAGES + 1):
        url = (f"{BASE}/wp-json/wp/v2/posts?per_page={PER_PAGE}"
               f"&_fields=date,date_gmt,link,content"
               f"&after={REST_AFTER}&before={REST_BEFORE}&page={page}")
        items = None
        for attempt in range(2):
            status, text, _ = fetch(url)
            if status == 200 and text:
                try:
                    items = json.loads(text)
                    break
                except ValueError:
                    pass
            print(f"page {page}: status {status} (attempt {attempt + 1})", file=sys.stderr)
        if not items:
            if page == 1:
                raise RuntimeError("REST listing unavailable")
            break
        posts += len(items)
        for it in items:
            gmt = (it.get("date_gmt") or "")[:10]
            link = it.get("link") or ""
            if not link or not gmt or not (WIN_START <= gmt <= WIN_END):
                continue
            rendered = (it.get("content") or {}).get("rendered") or ""
            if plain_len(rendered) >= MIN_BODY:
                found.setdefault(link, gmt)
        if len(items) < PER_PAGE:
            break
        if min((i.get("date_gmt") or "9999")[:10] for i in items) < WIN_START:
            break
    print(f"REST: {posts} posts walked, {len(found)} articles kept", file=sys.stderr)
    return found


def main():
    found = walk()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(found.items())
    tmp = OUT.with_suffix(".tsv.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for url, d in rows:
            fh.write(f"{url}\t{d}\n")
    tmp.replace(OUT)
    by_day = {}
    for _, d in rows:
        by_day[d] = by_day.get(d, 0) + 1
    for d in sorted(by_day):
        print(f"{d}\t{by_day[d]}")
    print(f"TOTAL\t{len(rows)}\t{len(by_day)} days")


if __name__ == "__main__":
    main()
