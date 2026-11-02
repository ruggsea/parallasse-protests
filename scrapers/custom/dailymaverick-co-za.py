#!/usr/bin/env python3
"""Daily Maverick (dailymaverick.co.za) article URL lister for 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
  robots.txt is permissive (only wp-content/admin/disallow) and names
  https://www.dailymaverick.co.za/sitemap_index.xml.
  The index lists 75 child sitemaps (72 article-sitemapN.xml urlsets plus
  news/section/author sitemaps), each with a <lastmod>.
  Article URLs carry the publication date in the path:
  /article/YYYY-MM-DD-slug/  (also /opinionista/ and /cartoon/ paths).
  <lastmod> per URL can drift to the edit date, so the URL-path date is the
  date the site states for publication; it is used here and matches the page
  JSON-LD datePublished (spot-checked).
  Pruning: a child sitemap's <lastmod> is the max of its URLs' lastmods, and
  each URL's lastmod >= its publication date, so any child file holding an
  article published in the window must itself have lastmod >= window start.
  We fetch only children with lastmod >= 2026-09-25 (22 files, incl. the
  fresh Google-News news-sitemap.xml which covers the newest ~48h as a bonus).
"""
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.dailymaverick.co.za"
INDEX = BASE + "/sitemap_index.xml"
WINDOW_START = dt.date(2026, 9, 25)
WINDOW_END = dt.date(2026, 10, 25)
OUT = Path("data/urls_custom/dailymaverick-co-za.tsv")

DATE_IN_PATH = re.compile(r"/(20\d\d-\d\d-\d\d)-")


def main() -> int:
    status, text, _ = fetch(INDEX)
    if status != 200 or not text:
        print(f"FATAL: sitemap index failed (status {status})")
        return 1

    entries = re.findall(
        r"<sitemap>\s*<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", text
    )
    children = []
    for loc, lastmod in entries:
        if not loc.startswith(BASE):
            continue
        if lastmod and lastmod[:10] >= str(WINDOW_START):
            children.append(loc)
    print(f"index ok: {len(entries)} entries, {len(children)} recent sitemaps")

    found = {}  # url -> date
    for url in children:
        s, body, _ = fetch(url)
        if s != 200 or not body:
            print(f"  WARN: {url.split('/')[-1]} status {s}")
            continue
        for m in re.finditer(r"<loc>([^<]+)</loc>", body):
            u = m.group(1)
            dm = DATE_IN_PATH.search(u)
            if not dm:
                continue
            try:
                d = dt.date.fromisoformat(dm.group(1))
            except ValueError:
                continue
            if WINDOW_START <= d <= WINDOW_END and u not in found:
                found[u] = d
        print(f"  {url.split('/')[-1]} ok, total so far {len(found)}")

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")

    per_day = {}
    for d in found.values():
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} URLs to {OUT}")
    print("per-day counts:")
    for d in sorted(per_day):
        print(f"  {d.isoformat()} {per_day[d]}")
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        n = per_day.get(dt.date.fromisoformat(target), 0)
        flag = "OK" if n >= 15 else "BELOW-15"
        print(f"check {target}: {n} [{flag}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
