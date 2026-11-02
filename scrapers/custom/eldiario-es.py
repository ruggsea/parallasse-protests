#!/usr/bin/env python3
"""eldiario.es (Spain) article URL lister for a fixed date window.

Route (checked 2026-10-27):
  robots.txt -> Sitemap: /sitemap_index_25b87.xml
  The index lists one flat urlset per month:
      /sitemap_contents_YYYY_MM_25b87_001.xml
  Each <url> has <loc> and <lastmod>.  For eldiario.es <lastmod> carries the
  publication instant (Europe/Madrid offset, e.g. 2026-09-30T23:58:23+02:00);
  it matched the article page's JSON-LD "datePublished" / meta
  article:published_time on 20/20 sampled pages across 2026-09-30, 10-10 and
  10-20 (identical to the second on most, a few minutes later on the rest).
  /sitemap_google_news_25b87.xml only holds ~2 days; it is merged for extra
  coverage of the last day of the window.
  Rejected routes: /archivo/YYYY/MM/DD/ , /hemeroteca/... , /ultima-hora/ all
  404; the site RSS holds only 106 recent items; /api/ is robots-disallowed.

Output: data/urls_custom/eldiario-es.tsv  (URL <TAB> YYYY-MM-DD, no header)
"""

import os
import re
import sys
import time
import collections
import datetime as dt

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

HOST = "https://www.eldiario.es"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT = "data/urls_custom/eldiario-es.tsv"

ARTICLE_RE = re.compile(r"_\d+_\d+\.html$")
# paths that tend to be video / gallery stubs with little body text
SKIP_SEGMENTS = ("/videos/", "/fotogalerias/", "/live/", "/en-directo/",
                 "/hemeroteca/", "/ultima-hora/")


def get(url, tries=3, pause=3.0):
    """Polite fetch with a few retries; returns text or ''."""
    last = None
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # noqa: BLE001
            status, text = None, None
            last = "exc:%s" % exc
        if status == 200 and text:
            return text
        last = status
        if status in (404, 410, 403):
            # 403 is not a robots block but is worth one slow retry
            if status == 403 and i < tries - 1:
                time.sleep(pause * (i + 2))
                continue
            break
        time.sleep(pause * (i + 1))
    print("  ! %s -> %s" % (url, last), file=sys.stderr)
    return ""


def index_urls():
    """Sitemap files from the index, plus constructed month files as backup."""
    idx = get(HOST + "/sitemap_index_25b87.xml")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", idx or "")
    return locs


def month_files(locs):
    """Month content sitemaps covering the window (all shards if numbered)."""
    months = []
    d = START.replace(day=1)
    while d <= END:
        months.append("%04d_%02d" % (d.year, d.month))
        d = (d.replace(day=28) + dt.timedelta(days=5)).replace(day=1)
    chosen = []
    for m in months:
        found = sorted(l for l in locs
                       if re.search(r"sitemap_contents_%s_" % m, l))
        if not found:
            found = ["%s/sitemap_contents_%s_25b87_001.xml" % (HOST, m)]
        chosen.extend(found)
    print("month sitemaps: %d" % len(chosen))
    return chosen


def parse_urlset(xml, with_news_date=False):
    """Yield (loc, date_string) from a flat urlset."""
    out = []
    for block in re.findall(r"<url\b.*?</url>", xml or "", re.S):
        m = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
        if not m:
            continue
        loc = m.group(1)
        stamp = None
        if with_news_date:
            n = re.search(r"<news:publication_date>\s*([^<]+?)\s*</news:publication_date>",
                          block)
            if n:
                stamp = n.group(1)
        if not stamp:
            lm = re.search(r"<lastmod>\s*([^<]+?)\s*</lastmod>", block)
            if not lm:
                continue
            stamp = lm.group(1)
        mdate = re.match(r"(\d{4}-\d{2}-\d{2})", stamp)
        if mdate:
            out.append((loc, mdate.group(1)))
    return out


def keep(url, date_s):
    if not url.startswith(HOST + "/"):
        return False
    if not ARTICLE_RE.search(url):
        return False
    if any(seg in url for seg in SKIP_SEGMENTS):
        return False
    try:
        d = dt.date.fromisoformat(date_s)
    except ValueError:
        return False
    return START <= d <= END


def main():
    locs = index_urls()
    if not locs:
        print("sitemap index unavailable, using constructed month files",
              file=sys.stderr)

    rows = {}
    for sm in month_files(locs):
        xml = get(sm)
        pairs = parse_urlset(xml)
        added = 0
        for loc, date_s in pairs:
            if keep(loc, date_s) and loc not in rows:
                rows[loc] = date_s
                added += 1
        print("  %s -> %d urls, %d new in window" % (sm.rsplit("/", 1)[-1],
                                                    len(pairs), added))

    # news sitemap: only ~2 days of history, but it does carry the last day
    news = get(HOST + "/sitemap_google_news_25b87.xml")
    news_pairs = parse_urlset(news, with_news_date=True)
    added = 0
    for loc, date_s in news_pairs:
        if keep(loc, date_s) and loc not in rows:
            rows[loc] = date_s
            added += 1
    print("  news sitemap -> %d urls, %d new in window" % (len(news_pairs), added))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for url in sorted(rows, key=lambda u: (rows[u], u)):
            fh.write("%s\t%s\n" % (url, rows[url]))
    os.replace(tmp, OUT)

    per_day = collections.Counter(rows.values())
    print("wrote %d urls to %s" % (len(rows), OUT))
    d = START
    while d <= END:
        key = d.isoformat()
        print("  %s  %d" % (key, per_day.get(key, 0)))
        d += dt.timedelta(days=1)


if __name__ == "__main__":
    main()
