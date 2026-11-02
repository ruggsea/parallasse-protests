#!/usr/bin/env python3
"""RTL Nieuws (rtl.nl) article URLs for 2026-09-25 .. 2026-10-25.

Route: robots.txt names https://www.rtl.nl/sitemap-index.xml, a sitemapindex of
per-ISO-week urlsets (sitemap-2026-W39.xml ... sitemap-2026-W43.xml hold the
window).  Each weekly file lists only that week's articles with a <lastmod> that
is the publication time (== the page's JSON-LD datePublished, verified on
samples: 2026-09-30T21:04:46+00:00, 2026-10-10T21:17:08+00:00).  We keep only
real articles ("/artikel/" in the path, no advertorial/video pages: RTL's video
fragments and TV broadcasts carry no datePublished and little body text) and
only rows whose lastmod day falls inside the file's own week, which drops the
few articles whose lastmod was bumped by a later edit.

https://www.rtl.nl/sitemap-news.xml is added as a second source for the last
days of the window: it carries exact <news:publication_date> values but covers
only ~2.5 days, so it cannot replace the weekly files.

Output: data/urls_custom/rtl-nl.tsv, one "URL<TAB>YYYY-MM-DD" per line,
sorted by date then URL.
"""
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/rtl-nl.tsv"

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
BASE = "https://www.rtl.nl/"

URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.S)
LOC = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", re.S)
LASTMOD = re.compile(r"<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.S)
PUBDATE = re.compile(r"<news:publication_date>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.S)


def is_article(url: str) -> bool:
    if not url.startswith(BASE):
        return False
    if "/artikel/" not in url.split("?")[0]:
        return False
    if "/advertorial/" in url:
        return False
    return True


def week_files():
    """ISO weeks (Monday based) covering START..END, with one day of slack."""
    day = START - dt.timedelta(days=1)
    stop = END + dt.timedelta(days=1)
    seen = []
    while day <= stop:
        iso = day.isocalendar()
        key = (iso[0], iso[1])
        if key not in seen:
            seen.append(key)
        day += dt.timedelta(days=1)
    return seen


def main():
    rows = {}
    log = []

    for year, week in week_files():
        monday = dt.date.fromisocalendar(year, week, 1)
        sunday = monday + dt.timedelta(days=6)
        url = "%ssitemap-%d-W%02d.xml" % (BASE, year, week)
        status, text, _ = fetch(url)
        log.append("%s -> %s (%d bytes)" % (url, status, len(text or "")))
        if status != 200 or not text:
            continue
        kept = 0
        for block in URL_BLOCK.findall(text):
            lm = LASTMOD.search(block)
            lo = LOC.search(block)
            if not (lm and lo):
                continue
            if not is_article(lo.group(1)):
                continue
            day = dt.date.fromisoformat(lm.group(1))
            if not (monday <= day <= sunday):
                continue  # lastmod bumped by a later edit, not publish day
            if not (START <= day <= END):
                continue
            rows.setdefault(lo.group(1).strip(), day)
            kept += 1
        log.append("   %d rows in window" % kept)

    # second source: the news sitemap carries exact publication times
    status, text, _ = fetch(BASE + "sitemap-news.xml")
    log.append("%ssitemap-news.xml -> %s (%d bytes)" % (BASE, status, len(text or "")))
    if status == 200 and text:
        n = 0
        for block in URL_BLOCK.findall(text):
            pd = PUBDATE.search(block)
            lo = LOC.search(block)
            if not (pd and lo) or not is_article(lo.group(1)):
                continue
            day = dt.date.fromisoformat(pd.group(1))
            if START <= day <= END:
                rows.setdefault(lo.group(1).strip(), day)
                n += 1
        log.append("   %d rows in window" % n)

    items = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for url, day in items:
            f.write("%s\t%s\n" % (url, day.isoformat()))

    for line in log:
        print(line)
    per_day = {}
    for _, day in items:
        per_day[day] = per_day.get(day, 0) + 1
    print("wrote %d unique URLs to %s" % (len(items), OUT))
    for day in sorted(per_day):
        print("  %s  %d" % (day.isoformat(), per_day[day]))
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("target %s: %d" % (target, per_day.get(dt.date.fromisoformat(target), 0)))


if __name__ == "__main__":
    main()
