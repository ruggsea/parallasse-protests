#!/usr/bin/env python3
"""telquel-ma: list article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt of telquel.ma is `User-agent: * / Allow:/` (no Sitemap lines);
/sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml are 404 and /wp-json/wp/v2/posts
answers 401 (REST closed).  The WordPress RSS feed /feed/ works (200) and is
paginated with /feed/?paged=N, 100 items per page, strictly descending by
pubDate.  We walk the pages until every item on a page is older than the window
start, then keep the items inside the window.

Listed date = the YYYY/MM/DD segment of the article URL (the site's own archive
path, e.g. https://telquel.ma/2026/10/10/slug_1234), falling back to the date
part of the feed <pubDate> when the URL carries no date.
"""
import re
import sys
import os
import time
import datetime as dt

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://telquel.ma"
FEED = BASE + "/feed/?paged=%d"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT = "data/urls_custom/telquel-ma.tsv"
MAX_PAGES = 40

ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
LINK_RE = re.compile(r"<link>\s*(.*?)\s*</link>", re.S)
DATE_RE = re.compile(r"<pubDate>\s*(.*?)\s*</pubDate>", re.S)
PATH_DATE_RE = re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_pubdate(s):
    # e.g. "Mon, 26 Oct 2026 17:44:21 +0000"
    m = re.match(r"\w+,\s+(\d+)\s+(\w+)\s+(\d{4})\s+(\d\d):(\d\d):(\d\d)", s or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def url_date(url):
    m = PATH_DATE_RE.search(url)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def main():
    rows = {}          # url -> date
    pages = 0
    for page in range(1, MAX_PAGES + 1):
        url = FEED % page
        status, text = None, None
        for attempt in range(3):
            try:
                status, text, _ = fetch(url)
            except Exception as e:            # noqa: BLE001
                print("feed page %d attempt %d error: %s" % (page, attempt + 1, e),
                      file=sys.stderr)
                status, text = None, None
            if status == 200 and text:
                break
            time.sleep(3 * (attempt + 1))
        pages += 1
        if status != 200 or not text:
            print("feed page %d status %s -> stop" % (page, status), file=sys.stderr)
            break
        items = ITEM_RE.findall(text)
        if not items:
            print("feed page %d: no items -> stop" % page, file=sys.stderr)
            break
        oldest = None
        added = 0
        for it in items:
            lm = LINK_RE.search(it)
            if not lm:
                continue
            link = lm.group(1).strip()
            dm = DATE_RE.search(it)
            pub = parse_pubdate(dm.group(1)) if dm else None
            d = url_date(link) or pub
            if d is None:
                continue
            if oldest is None or d < oldest:
                oldest = d
            if START <= d <= END:
                if link not in rows:
                    rows[link] = d
                    added += 1
        print("page %d: %d items, oldest %s, +%d (total %d)"
              % (page, len(items), oldest, added, len(rows)), file=sys.stderr)
        if oldest is not None and oldest < START:
            break
        if added == 0 and oldest is None:
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as fh:
        for link, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            fh.write("%s\t%s\n" % (link, d.isoformat()))
            per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
    print("pages=%d wrote %d urls to %s" % (pages, len(rows), OUT))
    for day in sorted(per_day):
        print("  %s\t%d" % (day, per_day[day]))


if __name__ == "__main__":
    main()
