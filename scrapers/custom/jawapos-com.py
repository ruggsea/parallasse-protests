#!/usr/bin/env python3
"""List jawapos.com article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (permissive for non-Googlebot) -> https://www.jawapos.com/sitemap.xml
-> post-index.xml -> post-N.xml. The index only lists post-1..post-10 but the
server keeps serving post-11, post-12, ... strictly descending by lastmod,
100 URLs per file, so we walk N=1,2,... until a file's newest lastmod is
before the window start (then every later file is older still) or the server
stops answering 200.

Dates: every article URL embeds the publication date in its path as a
YYMMDD+NNNN code, e.g. /nasional/2610240134/... = 2026-10-24, and the page's
JSON-LD datePublished is WIB local time (UTC+7) whose date part matches that
code (verified on 2610240134: page says 2026-10-24T11:56:50+07:00, lastmod
2026-10-24T11:56:50Z where the Z is actually WIB). We list the date from the
URL code, falling back to the sitemap lastmod date part for URLs without the
code. The site publishes ~250-300 articles/day, so each day has far more than
15 URLs.
"""
import datetime
import os
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://www.jawapos.com"
OUT = "data/urls_custom/jawapos-com.tsv"

# /section/YYMMDDNNNN/slug  -> date from the 8-digit path code
URL_DATE = re.compile(r"/([0-9]{8})/")
URL_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>")
LMOD_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>")


def url_date(url):
    m = URL_DATE.search(url)
    if m:
        code = m.group(1)
        try:
            y, mo, d = int(code[0:2]) + 2000, int(code[2:4]), int(code[4:6])
            return datetime.date(y, mo, d)
        except ValueError:
            return None
    return None


def get_post(n):
    """Fetch post-n.xml, retrying 5xx/transient errors. Returns (status, text)."""
    for attempt in range(6):
        status, text, _ = fetch(f"{BASE}/post-{n}.xml")
        if status == 200:
            return 200, text
        if status == 404:
            return 404, None
        print(f"post-{n}.xml -> {status}, retry {attempt + 1} in {15 * (attempt + 1)}s", flush=True)
        time.sleep(15 * (attempt + 1))
    return status, None


def main():
    urls = {}  # url -> date
    n = 1
    while n <= 200:
        status, text = get_post(n)
        if status != 200:
            print(f"post-{n}.xml gave up after retries ({status}), stopping", flush=True)
            break
        locs = URL_RE.findall(text)
        lmods = LMOD_RE.findall(text)
        if not locs:
            print(f"post-{n}.xml -> 200 but no entries, stopping", flush=True)
            break
        # newest entry of this file: files are strictly descending by lastmod
        newest_lm = None
        if lmods and len(lmods) >= len(locs):
            newest_lm = lmods[0]
        newest = None
        if newest_lm:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", newest_lm)
            if m:
                newest = datetime.date(*map(int, m.groups()))
        if newest and newest < START:
            print(f"post-{n}.xml newest {newest} < window start, stopping", flush=True)
            break
        added = 0
        for i, url in enumerate(locs):
            if not url.startswith(f"{BASE}/"):
                continue
            d = url_date(url)
            if d is None and i < len(lmods):
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lmods[i])
                d = datetime.date(*map(int, m.groups())) if m else None
            if d is None or d < START or d > END:
                continue
            if url not in urls:
                urls[url] = d
                added += 1
        print(f"post-{n}.xml: {len(locs)} urls, +{added} in window", flush=True)
        n += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    for url, d in urls.items():
        per_day[d] = per_day.get(d, 0) + 1
    with open(OUT, "w") as f:
        for url in sorted(urls, key=lambda u: (urls[u], u)):
            f.write(f"{url}\t{urls[url].isoformat()}\n")
    total = len(urls)
    print(f"wrote {total} urls to {OUT}")
    d = START
    while d <= END:
        ds = d.isoformat()
        print(f"{ds}: {per_day.get(d, 0)}")
        d += datetime.timedelta(days=1)
    for day in ("2026-09-30", "2026-10-10", "2026-10-20"):
        c = per_day.get(datetime.date.fromisoformat(day), 0)
        print(f"check {day}: {c} urls (need >=15)")


if __name__ == "__main__":
    main()
