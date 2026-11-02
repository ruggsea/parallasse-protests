#!/usr/bin/env python3
"""dnn-mn -- Odrьн сонин / dnn.mn (Mongolia) article URLs for 2026-09-25 .. 2026-10-25.

Route (probed 2026-10-27):
  * robots.txt -> HTTP 404 (unreachable) => assumed open, per fleet rule.
  * /sitemap.xml -> sitemapindex with 7 flat urlsets /sitemap/0 .. /sitemap/6.
    /sitemap/0 holds the 20 028 newest URLs descending by <lastmod>, back to 2023-11.
    Every recent article is there (are ~13-20 new URLs/day), so ONE sitemap file
    covers any 31-day window.
  * <lastmod> is UTC and it is the create/update timestamp (it equals the page
    dateModified, and it also equals the hex unix-epoch prefix of the new-style
    article id).  It is NOT reliably the publication date: the page states
    datePublished in +08:00 (Ulaanbaatar) and it can differ from lastmod by hours
    or a day.  So every candidate's article page is fetched and the listed date is
    the date part of its JSON-LD datePublished / meta article:published_time.
  * Candidates = every article whose lastmod >= start - 36 days (lastmod is never
    far behind datePublished, so that is a superset of in-window publications).

Writes data/urls_custom/dnn-mn.tsv  (URL<TAB>YYYY-MM-DD, no header, unique URLs).
"""
import sys
import os
import re
import html
import datetime
import collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT = "data/urls_custom/dnn-mn.tsv"

SITEMAP_INDEX = "https://dnn.mn/sitemap.xml"
CANDIDATE_BACKLOG_DAYS = 36   # lastmod buffer before START
MAX_PAGES = 1600              # safety cap on article fetches

RE_URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.S)
RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
RE_LASTMOD = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")
RE_DP = [
    re.compile(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})'),
    re.compile(r'\\"datePublished\\"\s*:\s*\\"(\d{4}-\d{2}-\d{2})'),
    re.compile(r'article:published_time"\s+content="(\d{4}-\d{2}-\d{2})'),
    re.compile(r'property="article:published_time"\s+content="(\d{4}-\d{2}-\d{2})'),
]


def day_of(s):
    """first YYYY-MM-DD inside a timestamp string, as a date"""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def sitemap_files():
    """read the index; fall back to the two files that cover the recent past"""
    files = []
    status, text, _ = fetch(SITEMAP_INDEX)
    if status == 200 and text:
        files = [html.unescape(u) for u in RE_LOC.findall(text)]
    if not files:
        files = ["https://dnn.mn/sitemap/0", "https://dnn.mn/sitemap/1"]
    # only the newest files can hold in-window articles, but keep a few
    return files[:4]


def candidates():
    """(url, lastmod date, lastmod string) for recent articles"""
    cutoff = START - datetime.timedelta(days=CANDIDATE_BACKLOG_DAYS)
    seen = {}
    for sm in sitemap_files():
        status, text, _ = fetch(sm)
        print(f"sitemap {sm}: HTTP {status}", file=sys.stderr)
        if status != 200 or not text:
            continue
        newest = None
        oldest = None
        for block in RE_URL_BLOCK.findall(text):
            lm = RE_LASTMOD.search(block)
            lo = RE_LOC.search(block)
            if not lo:
                continue
            url = html.unescape(lo.group(1))
            d = day_of(lm.group(1)) if lm else None
            if d is None:
                continue
            if newest is None or d > newest:
                newest = d
            if oldest is None or d < oldest:
                oldest = d
            if "/article/" not in url:
                continue
            if d < cutoff:
                continue
            seen.setdefault(url, (d, lm.group(1)))
        print(f"  urls kept so far {len(seen)}  lastmod range {oldest}..{newest}",
              file=sys.stderr)
    return seen


def page_date(url):
    status, text, _ = fetch(url)
    if status != 200 or not text:
        return None, status
    for rx in RE_DP:
        m = rx.search(text)
        if m:
            return day_of(m.group(1)), status
    return None, status


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cand = candidates()
    print(f"candidates: {len(cand)}", file=sys.stderr)

    rows = {}
    used_lastmod = 0
    missing = 0
    for i, (url, (lm_date, lm_str)) in enumerate(sorted(cand.items(),
                                                        key=lambda kv: kv[1][1],
                                                        reverse=True)):
        if i >= MAX_PAGES:
            print("page cap reached", file=sys.stderr)
            break
        d, status = page_date(url)
        if d is None:
            # page unreachable: fall back to the sitemap stamp shifted to +08:00
            missing += 1
            d = lm_date
            if lm_str.endswith("Z"):
                try:
                    utc = datetime.datetime.strptime(lm_str[:19], "%Y-%m-%dT%H:%M:%S")
                    d = (utc + datetime.timedelta(hours=8)).date()
                except ValueError:
                    pass
            used_lastmod += 1
        if START <= d <= END:
            rows.setdefault(url, d)
        if (i + 1) % 100 == 0:
            print(f"  fetched {i + 1}, kept {len(rows)}", file=sys.stderr)

    with open(OUT, "w") as f:
        for url in sorted(rows):
            f.write(f"{url}\t{rows[url].isoformat()}\n")

    per_day = collections.Counter(rows.values())
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"TOTAL {len(rows)} urls over {len(per_day)} days "
          f"(page-date fallbacks {used_lastmod}, unreadable {missing})",
          file=sys.stderr)
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"check {probe}: {per_day.get(datetime.date.fromisoformat(probe), 0)}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
