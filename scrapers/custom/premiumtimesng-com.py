#!/usr/bin/env python3
"""Premium Times (Nigeria) - premiumtimesng.com - article URLs published 2026-09-25..2026-10-25.

Route: the site's own WordPress REST API (Yoast sitemaps are STALE: every lastmod in
/sitemap_index.xml stops at 2026-06-23, so the sitemap tree carries no recent posts).

    GET /wp-json/wp/v2/posts?per_page=100&orderby=date&order=desc
        &after=<start>&before=<end>&_fields=date,date_gmt,link&page=N

robots.txt: "User-agent: * / Disallow:" with "crawl-delay: 10" (honoured here: >=10 s between
requests to the host; polite_fetch does the robots check and logs every request).

Listed date = the date part of the REST field `date`, the site's own local (Africa/Lagos, +01:00)
publication time; `modified` is the edit time and is ignored.

Writes data/urls_custom/premiumtimesng-com.tsv as "URL<TAB>YYYY-MM-DD", no header, unique URLs.
"""
import datetime
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/premiumtimesng-com.tsv")

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

API = ("https://www.premiumtimesng.com/wp-json/wp/v2/posts"
       "?per_page=100&orderby=date&order=desc&_fields=date,date_gmt,link"
       "&after={after}&before={before}&page={page}")
CRAWL_DELAY = 10.0          # robots.txt crawl-delay: 10
_last = [0.0]


def throttle():
    wait = _last[0] + CRAWL_DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def get_json(url, tries=3):
    for attempt in range(tries):
        throttle()
        status, text, _robots = fetch(url)
        if status == 200 and text:
            try:
                return json.loads(text)
            except ValueError:
                pass
        if status in (-1, 400, 404):
            # robots disallow / WP page out of range / gone: do not retry
            return None
        if status in (429, 500, 502, 503, 504) or status is None:
            time.sleep(min(60, 15 * (attempt + 1)))
            continue
        if status == 404:
            return None
        time.sleep(min(60, 15 * (attempt + 1)))
    return None


def date_part(s):
    return (s or "")[:10]


def main():
    # Naive local times: WP reads after/before in the site timezone (Africa/Lagos, +01:00).
    # Percent-encoding matters: a literal "+" in a query string decodes to a space and WP
    # then rejects the date, which is why an explicit "+01:00" offset returns nothing.
    after = urllib.parse.quote("{}T00:00:00".format((START - datetime.timedelta(days=2)).isoformat()))
    before = urllib.parse.quote("{}T00:00:00".format((END + datetime.timedelta(days=2)).isoformat()))

    rows = {}           # url -> YYYY-MM-DD
    page = 1
    pages_read = 0
    while page <= 120:
        url = API.format(after=after, before=before, page=page)
        data = get_json(url)
        if data is None:
            print("page {}: no data (stopping)".format(page))
            break
        if not isinstance(data, list) or not data:
            break
        pages_read += 1
        oldest = None
        for post in data:
            link = (post.get("link") or "").strip()
            d = date_part(post.get("date"))
            if not link or len(d) != 10:
                continue
            oldest = d if oldest is None else min(oldest, d)
            try:
                dd = datetime.date.fromisoformat(d)
            except ValueError:
                continue
            if START <= dd <= END:
                rows.setdefault(link, d)
        print("page {}: {} posts, oldest {} (total kept {})".format(
            page, len(data), oldest, len(rows)))
        if oldest is not None and oldest < START.isoformat():
            break
        if len(data) < 100:
            break
        page += 1

    # Safety net: if any target day is thin, ask for that day directly.
    targets = [datetime.date(2026, 9, 30), datetime.date(2026, 10, 10),
               datetime.date(2026, 10, 20)]
    for day in targets:
        have = sum(1 for d in rows.values() if d == day.isoformat())
        if have >= 15:
            continue
        a = urllib.parse.quote("{}T00:00:00".format(day.isoformat()))
        b = urllib.parse.quote("{}T00:00:00".format((day + datetime.timedelta(days=1)).isoformat()))
        for p in (1, 2, 3):
            data = get_json(API.format(after=a, before=b, page=p))
            if not data:
                break
            for post in data:
                link = (post.get("link") or "").strip()
                d = date_part(post.get("date"))
                if link and len(d) == 10:
                    try:
                        dd = datetime.date.fromisoformat(d)
                    except ValueError:
                        continue
                    if START <= dd <= END:
                        rows.setdefault(link, d)
            if len(data) < 100:
                break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for u in sorted(rows, key=lambda x: (rows[x], x)):
            f.write("{}\t{}\n".format(u, rows[u]))
    os.replace(tmp, OUT)

    per_day = {}
    for d in rows.values():
        per_day[d] = per_day.get(d, 0) + 1
    print("wrote {} urls from {} pages to {}".format(len(rows), pages_read, OUT))
    day = START
    while day <= END:
        k = day.isoformat()
        print("  {}  {}".format(k, per_day.get(k, 0)))
        day += datetime.timedelta(days=1)


if __name__ == "__main__":
    main()
