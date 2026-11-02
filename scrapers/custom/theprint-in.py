#!/usr/bin/env python3
"""ThePrint (theprint.in) article URLs for 2026-09-25..2026-10-25.

Route: robots.txt (permissive, allows sitemaps) -> /sitemap_index.xml (Yoast
index, 1291 entries) -> numbered post sitemaps /post-sitemap<N>.xml.
Numbering is chronological (post-sitemap.xml is the OLDEST batch, 2006-2017;
post-sitemap1235.xml the newest). Each numbered file holds ~350-1000 urls
ascending by time, each with <loc> + <lastmod>. The index's per-file <lastmod>
is the newest entry in that file, so every file whose index lastmod is older
than the window start can be skipped whole; the rest are fetched and filtered
per URL.

The site's own WP REST (/wp-json/wp/v2/posts) and date archives (/2026/10/20/)
answer with a Cloudflare "Just a moment..." JS challenge, so they are unusable
by a plain fetcher. The sitemaps are NOT challenged. Theprint.in's sitemap
responses are big (150-400 KB) and the origin frequently exceeds 30 s, so every
fetch here is retried with backoff and a global deadline guards the 20 min cap.

Listed date = date part of the sitemap <lastmod> (site-stated), checked against
the article page's JSON-LD datePublished on samples.
"""
import os
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/theprint-in.tsv")
INDEX = "https://theprint.in/sitemap_index.xml"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
BUDGET_S = 16 * 60          # stop fetching sitemaps after this (20 min hard cap)
T0 = time.time()


def get(url, tries=5):
    """polite_fetch with patient retries; theprint's origin times out a lot."""
    status, text, _ = 0, None, None
    for i in range(tries):
        if time.time() - T0 > BUDGET_S:
            return status, text
        status, text, _ = fetch(url)
        if status == 200 and text:
            return status, text
        if status in (-1, 404, 410):
            return status, text
        time.sleep(3 + 3 * i)
    return status, text


def iso_date(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def main():
    status, text = get(INDEX, tries=6)
    if not text:
        print("index fetch failed, status %s" % status, file=sys.stderr)
        return 1
    entries = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text)
    files = []
    for loc, lastmod in entries:
        m = re.search(r"/post-sitemap(\d*)\.xml$", loc)
        if not m:
            continue
        n = int(m.group(1) or 1)
        files.append((n, loc, iso_date(lastmod)))
    files.sort()
    print("index: %d post sitemaps" % len(files))

    # files are chronological: a file whose newest entry is before the window
    # start cannot hold an in-window url.
    wanted = [(n, loc) for n, loc, d in files if d is None or d >= START]
    print("fetching %d files covering the window" % len(wanted))

    rows = {}
    for n, loc in wanted:
        st, body = get(loc)
        if not body:
            print("  sitemap %d FAILED status %s" % (n, st), file=sys.stderr)
            continue
        pairs = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", body)
        kept = 0
        for url, lastmod in pairs:
            d = iso_date(lastmod)
            if d is None or not (START <= d <= END):
                continue
            rows[url.strip()] = d.isoformat()
            kept += 1
        print("  sitemap %d: %d urls, %d in window" % (n, len(pairs), kept))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(rows):
            d = rows[url]
            f.write("%s\t%s\n" % (url, d))
            per_day[d] = per_day.get(d, 0) + 1

    print("wrote %d unique urls to %s" % (len(rows), OUT))
    day = START
    while day <= END:
        k = day.isoformat()
        print("  %s\t%d" % (k, per_day.get(k, 0)))
        day += timedelta(days=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
