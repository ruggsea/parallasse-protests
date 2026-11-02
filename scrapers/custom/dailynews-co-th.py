#!/usr/bin/env python3
"""dailynews.co.th (Daily News, Thailand) — article URLs for 2026-09-25..2026-10-25.

Route: robots.txt is permissive (only /wp-admin/, /search/, /tags/, feeds disallowed).
The site is WordPress. The pretty REST path /wp-json/wp/v2/<type> is capped to 10 items
per page by a site filter, but the SAME controller answers uncapped through the query
form /?rest_route=/wp/v2/<type> (per_page=100 honoured). Two post types carry editorial
content with stable permalinks: 'news' (/news/<id>/, ~200/day) and 'article'
(/articles/<id>/, ~12/day).

Listed date = date part of the REST 'date' field (site local time, Asia/Bangkok +07:00).
Checked against the page JSON-LD datePublished: same instant rendered in +00:00, i.e. at
most one calendar day apart (inside the check's +/-1 day tolerance).

The REST 'content' field is used to drop very short items so that every listed URL
re-fetches to a real article body (>1500 chars of text).

Writes data/urls_custom/dailynews-co-th.tsv : URL<TAB>YYYY-MM-DD, no header, unique.
"""
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/dailynews-co-th.tsv")

SITE = "https://www.dailynews.co.th/"
START, END = "2026-09-25", "2026-10-25"
# one-day margins around the window, in site local time
AFTER = "2026-09-24T00:00:00"
BEFORE = "2026-10-26T00:00:00"
TYPES = ["news", "article"]
MIN_TEXT = 2500          # chars of post body (REST content) to keep a URL, so that even
                         # a body-only text extraction clears 1500 chars
MAX_PAGES = 200


def strip_tags(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def rest_page(ptype, page):
    url = (SITE + "?rest_route=/wp/v2/" + ptype +
           "&per_page=100&page=%d&_fields=date,link,content" % page +
           "&orderby=date&order=asc" +
           "&after=" + AFTER + "&before=" + BEFORE)
    status, body, _ = fetch(url)
    if status != 200 or not body:
        return status, None
    try:
        data = json.loads(body)
    except Exception:
        return status, None
    if not isinstance(data, list):
        return status, None
    return status, data


def collect():
    rows = {}            # url -> date
    for ptype in TYPES:
        page = 1
        got = 0
        while page <= MAX_PAGES:
            status, items = rest_page(ptype, page)
            if items is None:
                print("  %s page %d: status %s, stop" % (ptype, page, status))
                break
            if not items:
                break
            for it in items:
                link = it.get("link")
                date = (it.get("date") or "")[:10]
                if not link or not date:
                    continue
                if not (START <= date <= END):
                    continue
                try:
                    text = strip_tags((it.get("content") or {}).get("rendered", ""))
                except Exception:
                    text = ""
                if len(text) < MIN_TEXT:
                    continue
                rows[link] = date
            got += len(items)
            print("  %s page %d: %d items (cum %d, kept %d)"
                  % (ptype, page, len(items), got, len(rows)))
            if len(items) < 100:
                break
            page += 1
    return rows


def sitemap_fallback(rows):
    """Last resort: the Yoast article sitemaps (lower coverage, same date field)."""
    if rows:
        return rows
    print("REST gave nothing, falling back to article sitemaps")
    for name in ("article-sitemap28.xml", "article-sitemap27.xml"):
        status, body, _ = fetch(SITE + name)
        if status != 200 or not body:
            print("  %s status %s" % (name, status))
            continue
        for loc, lastmod in re.findall(
                r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", body, re.S):
            d = lastmod[:10]
            if START <= d <= END:
                rows[loc.strip()] = d
        print("  %s -> %d urls" % (name, len(rows)))
    return rows


def main():
    t0 = time.time()
    rows = collect()
    rows = sitemap_fallback(rows)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    for url, date in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
        per_day[date] = per_day.get(date, 0) + 1
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for url, date in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write("%s\t%s\n" % (url, date))
    os.replace(tmp, OUT)

    print("wrote %d urls to %s in %.0fs" % (len(rows), OUT, time.time() - t0))
    for d in sorted(per_day):
        print("  %s\t%d" % (d, per_day[d]))
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("check day %s: %d" % (d, per_day.get(d, 0)))


if __name__ == "__main__":
    main()
