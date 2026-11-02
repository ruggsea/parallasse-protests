#!/usr/bin/env python3
"""BusinessWorld (Philippines) - bworldonline.com

Lists article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt is fully permissive ("User-agent: * / Allow: /") and names no
sitemap. The site is WordPress, so the WP REST API is open:

    /wp-json/wp/v2/posts?per_page=100&page=N&_fields=link,date,date_gmt
        &after=...&before=...

`date` is the site-local (Asia/Manila, UTC+8) publication time and its date part
is the listed date. The article path also carries /<section>/YYYY/MM/DD/<id>/<slug>/
which agrees with it; we fall back to the path date only if the REST record is
missing. Pages are walked newest-first and we stop once a page's oldest post is
older than the window.

Fallback (only if the REST API refuses): WordPress core sitemaps
/wp-sitemap-posts-post-N.xml, newest first, dated by <lastmod>.
"""

import datetime
import json
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

OUT = "data/urls_custom/bworldonline-com.tsv"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
API = "https://www.bworldonline.com/wp-json/wp/v2/posts"
SITEMAP = "https://bworldonline.com/wp-sitemap-posts-post-%d.xml"
UA_DATE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def clean(t):
    return (t or "").lstrip("\ufeff")


def date_from_path(link):
    m = UA_DATE.search(link)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def in_window(d):
    return d is not None and START <= d <= END


def via_rest(rows):
    after = (START - datetime.timedelta(days=1)).isoformat() + "T00:00:00"
    before = (END + datetime.timedelta(days=1)).isoformat() + "T23:59:59"
    for page in range(1, 80):
        url = (
            "%s?per_page=100&page=%d&orderby=date&order=desc"
            "&_fields=link,date,date_gmt&after=%s&before=%s"
            % (API, page, after, before)
        )
        st, tx, _ = fetch(url)
        if st != 200 or not tx:
            print("  REST page %d -> %s, stopping" % (page, st))
            break
        try:
            data = json.loads(clean(tx))
        except Exception as exc:
            print("  REST page %d unparsable (%s), stopping" % (page, exc))
            break
        if not isinstance(data, list) or not data:
            break
        oldest = None
        for it in data:
            link = (it.get("link") or "").strip()
            if not link:
                continue
            d = None
            raw = it.get("date") or ""
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
            if m:
                try:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    d = None
            if d is None:
                d = date_from_path(link)
            if d is not None and (oldest is None or d < oldest):
                oldest = d
            if in_window(d):
                rows[link] = d.isoformat()
        print("  REST page %d: %d items, oldest %s, kept %d"
              % (page, len(data), oldest, len(rows)))
        if oldest is not None and oldest < START:
            break
        if len(data) < 100:
            break
    return rows


def via_sitemap(rows):
    for n in range(1, 40):
        st, tx, _ = fetch(SITEMAP % n)
        if st != 200 or not tx:
            print("  sitemap %d -> %s, stopping" % (n, st))
            break
        entries = re.findall(
            r"<url>\s*<loc>(.*?)</loc>(.*?)</url>", tx, re.S)
        if not entries:
            break
        oldest = None
        for loc, rest in entries:
            link = loc.strip()
            m = re.search(r"<lastmod>(\d{4})-(\d{2})-(\d{2})", rest)
            d = None
            if m:
                try:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    d = None
            if d is None:
                d = date_from_path(link)
            if d is not None and (oldest is None or d < oldest):
                oldest = d
            if in_window(d):
                rows.setdefault(link, d.isoformat())
        print("  sitemap %d: %d urls, oldest %s, kept %d"
              % (n, len(entries), oldest, len(rows)))
        if oldest is not None and oldest < START:
            break
    return rows


def main():
    rows = {}
    print("route: WP REST API")
    via_rest(rows)
    if len(rows) < 200:
        print("REST thin (%d urls), trying WP core sitemaps" % len(rows))
        via_sitemap(rows)

    # drop non-article endpoints that occasionally leak in (first path segment only,
    # so a slug that happens to contain e.g. "page" is never dropped)
    drop = re.compile(r"^https?://(?:www\.)?bworldonline\.com/(page|feed|amp|tag|category|author)/")
    final = {u: d for u, d in rows.items() if not drop.search(u)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as fh:
        for u in sorted(final):
            d = final[u]
            fh.write("%s\t%s\n" % (u, d))
            per_day[d] = per_day.get(d, 0) + 1

    print("%d urls written to %s" % (len(final), OUT))
    day = START
    while day <= END:
        k = day.isoformat()
        print("  %s  %d" % (k, per_day.get(k, 0)))
        day += datetime.timedelta(days=1)


if __name__ == "__main__":
    main()
