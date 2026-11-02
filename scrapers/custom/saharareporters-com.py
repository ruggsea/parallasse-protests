#!/usr/bin/env python3
"""List Sahara Reporters (saharareporters.com) article URLs published 2026-09-25..2026-10-25.

Route: the site's /more-latest-stories listing paginates chronologically via
?page=N (~36 article links per page, page 0 = newest, ~1.4 pages per day, so
the window needs ~40 pages). Article URLs carry the site's own publication
date in the path: /YYYY/MM/DD/slug. The article page also states the same
date in visible text ("<div>October 18, 2026</div>"), verified by spot-checks.
robots.txt (fetched 2026-10-26) is permissive: no Sitemap lines, /search/
disallowed, everything else allowed. The /news section page is a curated
top-stories feed (~5/day) and is NOT complete, so it is not used.

Writes data/urls_custom/saharareporters-com.tsv: URL<TAB>YYYY-MM-DD, no header,
unique URLs, sorted by date then URL.
"""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/saharareporters-com.tsv"
BASE = "https://saharareporters.com"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

ARTICLE_RE = re.compile(r'href="(/(20\d\d)/(0[1-9]|1[0-2])/([0-3][0-9])/[a-z0-9-]+?)"')


def dparse(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def main():
    found = {}
    stop = False
    page = 0
    while page < 70 and not stop:
        url = f"{BASE}/more-latest-stories?page={page}"
        status, body, _ = fetch(url)
        if status != 200 or not body:
            print(f"page {page}: status {status}, stopping", file=sys.stderr)
            break
        links = {}
        for path, y, m, d in ARTICLE_RE.findall(body):
            dt = dparse(y, m, d)
            if dt is not None:
                u = BASE + path
                links[u] = dt
        print(f"page {page}: status 200, {len(links)} article links", file=sys.stderr)
        if not links:
            break
        min_dt = min(links.values())
        max_dt = max(links.values())
        if max_dt < START:
            print(f"page {page} fully before window (max {max_dt}), stopping", file=sys.stderr)
            break
        for u, dt in links.items():
            if START <= dt <= END:
                found.setdefault(u, dt)
        page += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted((u, d) for u, d in found.items())
    with open(OUT, "w") as f:
        for u, d in lines:
            f.write(f"{u}\t{d.isoformat()}\n")

    per_day = {}
    for _, d in lines:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(lines)} URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    missing = [d.isoformat() for d in per_day if per_day[d] < 15]
    print("days with <15 URLs:", missing if missing else "none")


if __name__ == "__main__":
    main()
