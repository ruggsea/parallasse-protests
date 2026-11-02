#!/usr/bin/env python3
"""Scrape article URLs published by Proceso (Mexico, proceso.com.mx) for a date window.

Route (verified 2026-10-26):
- robots.txt (200) is permissive: only /buscar and /preview/ disallowed, sitemaps allowed.
- /sitemap.xml (also /sitemaps/index.xml) lists per-month article sitemaps
  https://www.proceso.com.mx/sitemaps/articles/YYYY-MM.xml (200, flat urlset with <loc> + <lastmod>).
- Article permalinks embed the publication date: /<section>/YYYY/M/D/<slug>-<id>.html
  Verified against 1 article: datePublished (JSON-LD) 2026-09-30T17:58:00-06:00 == URL date 2026-09-30.
- <lastmod> in the sitemap is EDIT time (a 09-30 article carried lastmod 2026-10-01),
  so the URL path date is used as the listed date, not lastmod.

Output: data/urls_custom/proceso-com-mx.tsv, one line URL<TAB>YYYY-MM-DD, unique URLs, no header.
"""
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/proceso-com-mx.tsv"
BASE = "https://www.proceso.com.mx"

WIN_START = date(2026, 9, 25)
WIN_END = date(2026, 10, 25)

# months that can contain article dates in the window
MONTHS = ["2026-09", "2026-10"]

URL_RE = re.compile(r"<loc>\s*(https?://[^<\s]+\.html?)\s*</loc>")
DATE_RE = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/")


def parse_sitemap(text):
    """Return list of (url, date|None) from a sitemap body."""
    out = []
    for m in URL_RE.finditer(text or ""):
        url = m.group(1).split("?")[0].rstrip("/")
        dm = DATE_RE.search(url)
        d = None
        if dm:
            y, mo, dd = (int(x) for x in dm.groups())
            try:
                d = date(y, mo, dd)
            except ValueError:
                d = None
        out.append((url, d))
    return out


def main():
    seen = {}
    per_day = defaultdict(int)
    for month in MONTHS:
        url = f"{BASE}/sitemaps/articles/{month}.xml"
        status, text, _robots = fetch(url)
        if status != 200:
            print(f"WARNING: {url} -> HTTP {status}, skipping", file=sys.stderr)
            continue
        entries = parse_sitemap(text)
        print(f"{url}: {len(entries)} URLs")
        for aurl, d in entries:
            if d is None:
                continue
            if not (WIN_START <= d <= WIN_END):
                continue
            if aurl in seen:
                continue
            seen[aurl] = d
            per_day[d] += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for aurl, d in sorted(seen.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{aurl}\t{d.isoformat()}\n")

    print(f"wrote {len(seen)} URLs to {OUT}")
    print("per-day counts:")
    for d in sorted(per_day):
        print(f"  {d.isoformat()}\t{per_day[d]}")
    missing = [d for d in [WIN_START, date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20), WIN_END]
               if per_day.get(d, 0) < 15]
    if missing:
        print(f"WARNING: days with <15 URLs: {[d.isoformat() for d in missing]}", file=sys.stderr)


if __name__ == "__main__":
    main()
