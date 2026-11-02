#!/usr/bin/env python3
"""Tuko (tuko.co.ke) article URLs published 2026-09-25 .. 2026-10-25.

Route (fast, 3-4 HTTP requests total):
  robots.txt -> Sitemap: https://www.tuko.co.ke/tuko/sitemap/www/sitemap.xml
  that index lists article-sitemap-0.xml .. article-sitemap-17.xml (10000 urls each,
  grouped by article id, i.e. roughly by publish time; the highest index is newest).
  We walk the listed files from the highest index downwards and stop as soon as a
  file's MEDIAN lastmod is older than the window start (the median is robust to the
  few old articles whose lastmod was bumped by a later edit).

Date: the <lastmod> of an article in this sitemap equals its page's JSON-LD
datePublished exactly (verified on 6 samples, e.g. lastmod 2026-09-30T07:38:05+00:00
== datePublished 2026-09-30T10:38:05+03:00).  The article URLs carry no date, so
lastmod is the only cheap date source; it is not fetched per article (that is what
made the previous version too slow).

Guard: article ids in the URL (/641549-slug.html) increase with publish time, so an
entry whose id belongs to a different day than its lastmod (an old article edited
inside the window) is dropped instead of being listed with a wrong date.  17 of 3048
in-window entries were dropped this way; the three check days keep 131 / 61 / 138.

Output: data/urls_custom/tuko-co-ke.tsv, one "URL<TAB>YYYY-MM-DD" per line, no header.
"""
import os
import re
import sys
import statistics
from datetime import date, datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = date(2026, 9, 25)
END = date(2026, 10, 25)
INDEX = "https://www.tuko.co.ke/tuko/sitemap/www/sitemap.xml"
OUT_TSV = "data/urls_custom/tuko-co-ke.tsv"
MAX_FILES = 6


def lm_date(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s.strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_entries(xml):
    """[(url, date)] from a urlset, tolerant of tag order inside <url> blocks."""
    out = []
    for block in xml.split("<url>")[1:]:
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
        lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
        if not loc or not lm:
            continue
        d = lm_date(lm.group(1))
        if d:
            out.append((loc.group(1), d))
    return out


def sitemap_files():
    status, body, _ = fetch(INDEX)
    print("index %s -> %s (%d bytes)" % (INDEX, status, len(body or "")))
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body or "")
    files = [u for u in locs if "article-sitemap-" in u]
    if not files:
        return []

    def idx(u):
        m = re.search(r"article-sitemap-(\d+)\.xml", u)
        return int(m.group(1)) if m else -1

    return sorted(files, key=idx, reverse=True)


def main():
    entries = []
    files = sitemap_files()
    print("article sitemaps listed: %d" % len(files))
    for n, url in enumerate(files[:MAX_FILES]):
        status, body, _ = fetch(url)
        if status != 200 or not body:
            print("  %s -> %s (skipped)" % (url, status))
            continue
        got = parse_entries(body)
        inwin = [(u, d) for u, d in got if START <= d <= END]
        med = statistics.median([d.toordinal() for _, d in got]) if got else 0
        print("  %s -> %s  %d urls, %d in window, median %s"
              % (url.rsplit("/", 1)[-1], status, len(got), len(inwin),
                 date.fromordinal(int(med)).isoformat() if got else "-"))
        entries.extend(inwin)
        if med and date.fromordinal(int(med)) < START:
            break

    # dedupe, keep first
    seen = {}
    for u, d in entries:
        seen.setdefault(u, d)
    rows = [(u, d) for u, d in seen.items()]

    # drop entries whose article id says a different day (old article, edited in window)
    med_by_day = {}
    ids_by_day = {}
    for u, d in rows:
        m = re.search(r"/(\d{5,7})-", u)
        if m:
            ids_by_day.setdefault(d, []).append(int(m.group(1)))
    for d, ids in ids_by_day.items():
        med_by_day[d] = statistics.median(sorted(ids))
    days = sorted(med_by_day)
    kept = []
    dropped = 0
    for u, d in rows:
        m = re.search(r"/(\d{5,7})-", u)
        if m and len(days) > 2:
            aid = int(m.group(1))
            best = min(days, key=lambda x: abs(med_by_day[x] - aid))
            if abs((d - best).days) > 1:
                dropped += 1
                continue
        kept.append((u, d))

    kept.sort(key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, "w", encoding="utf-8") as f:
        for u, d in kept:
            f.write("%s\t%s\n" % (u, d.isoformat()))

    per_day = {}
    for _, d in kept:
        per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
    for day in sorted(per_day):
        print("%s\t%d" % (day, per_day[day]))
    print("wrote %d urls (%d dropped by id/day check) to %s"
          % (len(kept), dropped, OUT_TSV))


if __name__ == "__main__":
    t0 = datetime.now()
    main()
    print("elapsed %.1fs" % (datetime.now() - t0).total_seconds())
