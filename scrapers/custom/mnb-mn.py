#!/usr/bin/env python3
"""mnb.mn (Mongolian National Broadcaster) article URLs for a date window.

Route: the site is a Next.js app.  /news?page=N is the chronological archive,
newest first, ~24 articles per page, one page per publishing day.  Each page
embeds its article list as an RSC payload array
  {"articles":[{"id":"<slug>","title":...,"publishedIso":"2026-09-30T00:22:36.912Z",...}]}
so one request yields both the URL (/article/<slug>) and the publication time.
The site displays dates in Mongolia time (UTC+8); publishedIso is UTC, so the
listed date is the UTC+8 date of publishedIso.

Sitemaps (/sitemap/0..29.xml) exist but their <lastmod> is a crawl/regeneration
timestamp (30 shards x 10,000 URLs, all lastmod inside a single day), so they
are useless for dating and only cover roughly the last two weeks anyway.
robots.txt allows /news and /article/*; it only disallows /search, /article$
(the bare path) and /design-system.

Usage: python3 scrapers/custom/mnb-mn.py
Writes data/urls_custom/mnb-mn.tsv  (URL<TAB>YYYY-MM-DD, no header)
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.mnb.mn"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
LOCAL_OFFSET = dt.timedelta(hours=8)  # Asia/Ulaanbaatar, no DST
OUT = "data/urls_custom/mnb-mn.tsv"
MAX_PAGES = 80


def extract_articles(html):
    """Pull the 'articles' array out of the Next.js RSC payload (quotes are backslash-escaped)."""
    key = 'articles\\":['
    i = html.find(key)
    if i < 0:
        return []
    start = i + len(key) - 1
    depth = 0
    j = start
    n = len(html)
    while j < n:
        c = html[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    raw = html[start:j]
    try:
        return json.loads(raw.replace('\\"', '"'))
    except ValueError:
        return []


def local_date(iso):
    """UTC ISO timestamp -> Mongolia (UTC+8) date."""
    try:
        ts = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return (ts + LOCAL_OFFSET).date()


def fallback_pairs(html):
    """Plain-HTML fallback: article hrefs paired with the nearest following date text."""
    out = []
    for m in re.finditer(r'href="(/article/[a-z0-9][a-z0-9-]+)"', html):
        tail = html[m.end():m.end() + 4000]
        d = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", tail)
        if not d:
            continue
        try:
            day = dt.date(int(d.group(1)), int(d.group(2)), int(d.group(3)))
        except ValueError:
            continue
        out.append((BASE + m.group(1), day))
    return out


def main():
    rows = {}
    pages_done = 0
    for page in range(1, MAX_PAGES + 1):
        url = BASE + "/news?page=%d" % page
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup: stop with what we have
            print("fetch error page %d: %s" % (page, exc))
            break
        if status != 200 or not text:
            print("page %d status %s - stop" % (page, status))
            break
        pages_done += 1
        arts = extract_articles(text)
        pairs = []
        for a in arts:
            slug = a.get("id")
            iso = a.get("publishedIso")
            if not slug or not iso:
                continue
            day = local_date(iso)
            if day is None:
                continue
            pairs.append((BASE + "/article/" + slug, day))
        if not pairs:
            pairs = fallback_pairs(text)
        if not pairs:
            print("page %d: no articles parsed - stop" % page)
            break
        new = 0
        for u, day in pairs:
            if START <= day <= END and u not in rows:
                rows[u] = day
                new += 1
        oldest = min(d for _, d in pairs)
        print("page %d: %d articles, %d new in window, oldest %s" % (page, len(pairs), new, oldest))
        if oldest < START:
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    items = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as fh:
        for u, day in items:
            fh.write("%s\t%s\n" % (u, day.isoformat()))

    print("pages fetched: %d, urls written: %d" % (pages_done, len(items)))
    counts = {}
    for _, day in items:
        counts[day] = counts.get(day, 0) + 1
    d = START
    while d <= END:
        print("%s\t%d" % (d.isoformat(), counts.get(d, 0)))
        d += dt.timedelta(days=1)


if __name__ == "__main__":
    main()
