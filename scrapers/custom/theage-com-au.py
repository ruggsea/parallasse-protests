#!/usr/bin/env python3
"""The Age (theage.com.au) article URLs for 2026-09-25..2026-10-25.

Route (robots.txt allows / for generic agents, names the sitemaps):
  1. /sitemaps/theage-sitemaps-articles.xml  -> index of per-day files
     /sitemaps/theage-articles-YYYYMMDD.xml, each listing articles
     LASTMOD'd on that day (article URLs carry the true publish date
     as ...slug-YYYYMMDD-pXXXX.html).
  2. Union of every per-day file from 20260925 through the newest in the
     index (<= today), then keep only URLs whose slug date falls inside
     the window.  An article published in the window is lastmod'd on or
     after its publish day, so it appears in some fetched file.
Date listed = the YYYYMMDD in the URL slug (The Age's own publish date,
AEST; equals page JSON-LD datePublished on sample checks).
"""
import datetime as dt
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://www.theage.com.au"
INDEX = BASE + "/sitemaps/theage-sitemaps-articles.xml"
WIN_START = dt.date(2026, 9, 25)
WIN_END = dt.date(2026, 10, 25)
TODAY = dt.date.today()
OUT = "data/urls_custom/theage-com-au.tsv"

DAY_RE = re.compile(r"theage-articles-(\d{8})\.xml")
URL_DATE_RE = re.compile(r"-(\d{8})-p[0-9a-zA-Z]+\.html$")
HTML_RE = re.compile(r"(https://www\.theage\.com\.au/[^<\s]+?\.html)")


def parse_date(s):
    try:
        return dt.datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def main():
    status, text, _ = fetch(INDEX)
    if status != 200 or not text:
        print(f"index fetch failed: {status}")
        sys.exit(1)

    files = sorted(set(DAY_RE.findall(text)))
    todo = []
    for d in files:
        dd = parse_date(d)
        if dd and WIN_START <= dd <= max(WIN_END, TODAY):
            todo.append(d)
    print(f"per-day sitemap files to fetch: {len(todo)} ({todo[0]}..{todo[-1]})")

    urls = {}  # url -> date
    for d in todo:
        status, text, _ = fetch(f"{BASE}/sitemaps/theage-articles-{d}.xml")
        if status != 200 or not text:
            print(f"  {d}: HTTP {status} (skipped)")
            continue
        n = 0
        for u in HTML_RE.findall(text):
            m = URL_DATE_RE.search(u)
            if not m:
                continue
            pd = parse_date(m.group(1))
            if pd and WIN_START <= pd <= WIN_END:
                if u not in urls:
                    urls[u] = pd
                    n += 1
        print(f"  {d}: {n} in-window new urls")

    # de-dup: a URL may appear with its slug date; keep first
    rows = sorted(urls.items(), key=lambda kv: (kv[1], kv[0]))
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")
    print(f"total unique urls: {len(rows)}")
    per = {}
    for _, d in rows:
        per[d] = per.get(d, 0) + 1
    for d in sorted(per):
        print(d, per[d])
    for need in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {need}: {per.get(dt.date.fromisoformat(need), 0)}")


if __name__ == "__main__":
    main()
