#!/usr/bin/env python3
"""Ham-Mihan (hammihanonline.ir) article URL list, 2026-09-25..2026-10-25.

Route: robots.txt is permissive and names https://hammihanonline.ir/sitemap.xml,
an index of per-DAY sitemaps whose <loc> encodes the date in base64:
  /sitemap/<b64({"model":"newsstudioDateRange","date":"YYYY-MM-DD"})>.xml
Each file lists that day's articles with <lastmod> == publication time (verified:
JSON-LD datePublished on the article page matches the sitemap lastmod to the
second, e.g. 2026-09-30T04:30:21Z).

Article pages are addressed by id. The long Persian-slug canonical URLs
(/بخش-.../<id>-<slug>) time out from our host (connection reset, status 0 after
many retries), but the site's own RSS feed (https://hammihanonline.ir/feeds/)
serves every article at the short URL https://hammihanonline.ir/fa/tiny/news-<id>,
which fetches fine (full article text, JSON-LD datePublished present). We therefore
emit the /fa/tiny/news-<id> form: same article, stable, fetchable.

Listed date = the <lastmod> date part from the day's sitemap (the site's stated
publication time); falls back to the sitemap's own day if lastmod is absent.
"""
import base64
import datetime as dt
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT = "data/urls_custom/hammihanonline-ir.tsv"

URL_RE = re.compile(r"<loc>(.*?)</loc>")
LM_RE = re.compile(r"<lastmod>(.*?)</lastmod>")
ID_RE = re.compile(r"/(\d+)-")


def day_sitemap(d: dt.date) -> str:
    payload = '{"model":"newsstudioDateRange","date":"%s"}' % d.isoformat()
    b = base64.b64encode(payload.encode()).decode()
    return "https://hammihanonline.ir/sitemap/%s.xml" % b


def main():
    found = {}  # tiny url -> date
    by_day = {}
    d = START
    while d <= END:
        url = day_sitemap(d)
        text = None
        for attempt in range(3):
            status, text, _ = fetch(url, cache=False)
            if status == 200 and text:
                break
            time.sleep(5)
        if status != 200 or not text:
            print("WARN: %s -> status %s" % (d.isoformat(), status), file=sys.stderr)
            d += dt.timedelta(days=1)
            continue
        locs = URL_RE.findall(text)
        lms = LM_RE.findall(text)
        n_new = 0
        for i, loc in enumerate(locs):
            m = ID_RE.search(loc)
            if not m:
                continue
            date = d.isoformat()
            if i < len(lms) and re.match(r"\d{4}-\d{2}-\d{2}", lms[i]):
                date = lms[i][:10]
            if not (START.isoformat() <= date <= END.isoformat()):
                continue
            tiny = "https://hammihanonline.ir/fa/tiny/news-%s" % m.group(1)
            if tiny not in found:
                found[tiny] = date
                n_new += 1
                by_day[date] = by_day.get(date, 0) + 1
        print("OK %s: file listed %d, %d new urls" % (d.isoformat(), len(locs), n_new))
        d += dt.timedelta(days=1)

    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(found):
            f.write("%s\t%s\n" % (url, found[url]))

    total = len(found)
    print("TOTAL %d unique urls" % total)
    d = START
    while d <= END:
        print("  %s: %d" % (d.isoformat(), by_day.get(d.isoformat(), 0)))
        d += dt.timedelta(days=1)


if __name__ == "__main__":
    main()
