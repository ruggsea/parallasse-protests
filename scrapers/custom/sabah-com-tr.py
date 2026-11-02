#!/usr/bin/env python3
"""Sabah (Turkey) scraper: article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt (200, permissive) names /sitemap/index.xml, which lists
/sitemap/post.xml, an index of per-month Yoast-style archive sitemaps:
    /sitemaparchives/post/2026-9.xml, 2026-9-1.xml, 2026-9-2.xml
    /sitemaparchives/post/2026-10.xml, 2026-10-1.xml, 2026-10-2.xml
Each file holds <=5000 <url><loc>+<lastmod> entries, sorted strictly DESCENDING
by publication time (the boundary timestamps across files are consecutive to
the second), and each month's file contains exactly the posts PUBLISHED in that
month. <lastmod> is the post modification time: for unedited posts it is the
publication timestamp itself (verified: page JSON-LD datePublished equals the
sitemap lastmod to the second on samples). For a few edited posts lastmod has
drifted into the next month; those are dropped (listed date would be the edit
date, not the publish date).

Listed date per URL:
  1. if the URL path contains /YYYY/MM/DD/ -> that date (site's own article
     URL scheme; verified equal to JSON-LD datePublished), else
  2. the <lastmod> date-part, accepted only if lastmod's month equals the
     file's month (i.e. the post was never edited after publishing).
All URLs are filtered to the window 2026-09-25..2026-10-25 and deduplicated.
"""
import re
import sys
import collections
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/sabah-com-tr.tsv"
START, END = "2026-09-25", "2026-10-25"

# Archive files covering the window (month-file names, page order old->new).
FILES = [
    "2026-9-1.xml",    # posts 09-12 -> 09-24  (tail covers 09-25 onward)
    "2026-9-2.xml",    # posts 09-24 09:33 -> 09-30
    "2026-10.xml",     # posts 10-01 -> 10-12
    "2026-10-1.xml",   # posts 10-12 -> 10-23
    "2026-10-2.xml",   # posts 10-23 -> present
]
BASE = "https://www.sabah.com.tr/sitemaparchives/post/"
URLDATE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
ENTRY = re.compile(r"<loc>(.*?)</loc>\s*<lastmod>(\d{4}-\d{2}-\d{2})T", re.S)


def main():
    urls = {}  # url -> date
    per_file = {}
    for f in FILES:
        status, text, _ = fetch(BASE + f)
        if status != 200 or not text:
            print(f"ERROR {f}: status {status}", file=sys.stderr)
            continue
        month = f.split(".xml")[0].split("-")[1]  # '9' or '10'
        entries = ENTRY.findall(text)
        kept = skipped = 0
        for loc, lastmod in entries:
            m = URLDATE.search(loc)
            if m:
                date = "-".join(m.groups())
            elif lastmod[:7] == f"2026-{int(month):02d}":
                date = lastmod
            else:
                skipped += 1  # edited after publishing: lastmod is not the publish date
                continue
            if START <= date <= END and loc not in urls:
                urls[loc] = date
                kept += 1
        per_file[f] = (len(entries), kept, skipped)
        print(f"{f}: {len(entries)} entries, kept {kept}, dropped edited {skipped}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    daily = collections.Counter(d for d in urls.values())
    with open(OUT, "w") as fh:
        for url, date in sorted(urls.items(), key=lambda kv: (kv[1], kv[0])):
            fh.write(f"{url}\t{date}\n")
    print(f"wrote {len(urls)} URLs to {OUT}")
    for day in sorted(daily):
        print(f"{day}: {daily[day]}")
    if len(daily) < 31:
        missing = [f"2026-{m:02d}-{d:02d}" for m in (9, 10)
                   for d in range(1, 31) if (f"2026-{m:02d}-{d:02d}" not in daily)
                   and START <= f"2026-{m:02d}-{d:02d}" <= END]
        print("days with no URLs:", missing)


if __name__ == "__main__":
    main()
