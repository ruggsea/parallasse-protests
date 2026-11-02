#!/usr/bin/env python3
"""Hürriyet Daily News (hurriyetdailynews.com) article URL lister.

Route: robots.txt is permissive and names
  https://www.hurriyetdailynews.com/sitemaps/posts.xml  (sitemapindex)
  https://www.hurriyetdailynews.com/sitemaps/newssitemap.xml  (last ~2 days)
The index lists per-month flat urlsets /sitemaps/posts-YYYY-MM.xml, newest first.
Each <url> has <loc> (article URL) and <lastmod> = PUBLISH instant (+03:00):
verified on 9 articles across the window that lastmod's date part equals the
page's JSON-LD datePublished date part (datePublished is the same clock time,
3 h earlier, i.e. UTC values carrying a +03:00 suffix).
The monthly file is rebuilt live (the index's lastmod lies, it said 10-24 while
the file already held 10-26), so no per-day URLs are needed.

Output: data/urls_custom/hurriyetdailynews-com.tsv  ->  URL<TAB>YYYY-MM-DD
"""

import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.hurriyetdailynews.com"
OUT = "data/urls_custom/hurriyetdailynews-com.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

RE_URL = re.compile(r"<url>(.*?)</url>", re.S)
RE_LOC = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", re.S)
RE_LASTMOD = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S)
RE_NEWSDATE = re.compile(r"<news:publication_date>\s*(.*?)\s*</news:publication_date>", re.S)


def month_keys(start, end):
    keys = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        keys.append("%04d-%02d" % (y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return keys


def parse_urlset(xml):
    """Yield (loc, date-string-or-None) for every <url> entry."""
    for block in RE_URL.findall(xml or ""):
        loc_m = RE_LOC.search(block)
        if not loc_m:
            continue
        loc = loc_m.group(1).strip()
        if not loc:
            continue
        d = None
        lm = RE_LASTMOD.search(block)
        if lm:
            d = lm.group(1).strip()
        else:
            nd = RE_NEWSDATE.search(block)
            if nd:
                d = nd.group(1).strip()
        yield loc, d


def in_window(day):
    return START <= day <= END


def main():
    found = {}  # url -> date

    # 1) per-month url sets
    for key in month_keys(START, END):
        url = "%s/sitemaps/posts-%s.xml" % (BASE, key)
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print("WARN %s -> %s" % (url, status), file=sys.stderr)
            continue
        n = 0
        for loc, d in parse_urlset(text):
            if not d:
                continue
            try:
                day = date.fromisoformat(d[:10])
            except ValueError:
                continue
            if not in_window(day):
                continue
            if loc not in found:
                found[loc] = day
                n += 1
        print("%s -> %d in-window urls" % (url, n), file=sys.stderr)

    # 2) news sitemap: covers the last couple of days, fills any lag in the
    #    monthly file; same publication_date semantics.
    status, text, _ = fetch("%s/sitemaps/newssitemap.xml" % BASE)
    if status == 200 and text:
        n = 0
        for loc, d in parse_urlset(text):
            if not d:
                continue
            try:
                day = date.fromisoformat(d[:10])
            except ValueError:
                continue
            if in_window(day) and loc not in found:
                found[loc] = day
                n += 1
        print("news sitemap -> +%d urls" % n, file=sys.stderr)
    else:
        print("WARN news sitemap -> %s" % status, file=sys.stderr)

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for url, day in rows:
            fh.write("%s\t%s\n" % (url, day.isoformat()))
    os.replace(tmp, OUT)

    per_day = {}
    for _, day in rows:
        per_day[day.isoformat()] = per_day.get(day.isoformat(), 0) + 1
    d = START
    while d <= END:
        k = d.isoformat()
        print("%s\t%d" % (k, per_day.get(k, 0)))
        d += timedelta(days=1)
    print("TOTAL %d urls -> %s" % (len(rows), OUT))


if __name__ == "__main__":
    main()
