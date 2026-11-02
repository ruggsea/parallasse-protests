#!/usr/bin/env python3
"""trome.com (Trome, Peru) - article URLs 2026-09-25..2026-10-25.

Route that works:
  robots.txt (200, permissive: "User-agent: * Disallow:") advertises
  https://trome.com/sitemap/?outputType=xml, a sitemapindex of 10 per-section
  sitemaps (celebrities, horoscopo, viral, mundo, usa, actualidad, deportes,
  familia, emprende-trome, impresa). Each is a flat urlset of <loc>+<lastmod>,
  ordered newest first. The five capped at 1000 entries all reach back well past
  2026-09-25 (oldest in-window files: actualidad 2026-09-03, deportes 2026-06-13),
  so 1 index + 10 fetches cover the whole window (~5600 entries, ~5500 unique).

Date source: <lastmod> in site-local time (America/Lima, -05:00, no DST).
Verified on 10 random in-window articles across 09-25/09-30/10-10/10-20/10-25:
the sitemap lastmod equals the page JSON-LD datePublished to the millisecond
(e.g. lastmod 2026-09-25T21:39-05:00 == page datePublished 2026-09-26T02:39:00Z),
i.e. lastmod is the publication timestamp, not edit time. The script re-checks a
fixed-seed sample of 25 final URLs against their pages at runtime and prints a
warning if any page date is more than 1 day off.

Duplicates: a few URLs appear in two section sitemaps (89 of 5610); where two
lastmods disagree the earlier one is kept.

Output: data/urls_custom/trome-com.tsv - "URL<TAB>YYYY-MM-DD", unique URLs, no
header. Standalone: python3 scrapers/custom/trome-com.py
"""
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/trome-com.tsv")
INDEX = "https://trome.com/sitemap/?outputType=xml"
START = "2026-09-25"
END = "2026-10-25"
ENTRY = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>", re.S)
PUB = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
META = re.compile(r'article:published_time"\s+content="([^"]+)"')
VERIFY_N = 25


def main():
    status, index, _ = fetch(INDEX)
    if status != 200 or not index:
        print(f"FATAL: sitemap index HTTP {status}", file=sys.stderr)
        sys.exit(1)
    sections = re.findall(r"<loc>\s*(https://trome\.com/sitemap/[^<]+?)\s*</loc>", index)
    print(f"index: {len(sections)} section sitemaps")

    # url -> earliest lastmod (they should agree; keep min as the publication time)
    items = {}
    for sec in sections:
        status, text, _ = fetch(sec)
        if status != 200 or not text:
            print(f"WARNING: {sec} HTTP {status}", file=sys.stderr)
            continue
        for loc, lm in ENTRY.findall(text):
            if loc in items:
                if lm < items[loc]:
                    items[loc] = lm
            else:
                items[loc] = lm
        print(f"  {sec.split('/sitemap/')[1][:35]:38s} +{len(ENTRY.findall(text))} entries")
    print(f"total unique URLs in sitemaps: {len(items)}")

    # filter to window, using the lastmod date in site-local -05:00 time
    rows = [(lm[:10], loc) for loc, lm in items.items() if START <= lm[:10] <= END]
    per_day = Counter(d for d, _ in rows)
    print(f"in window {START}..{END}: {len(rows)} URLs")

    # fixed-seed spot check: page date vs listed date (lastmod is publication time;
    # a re-edited article would show lastmod later than datePublished)
    rnd = random.Random(20261025)
    sample = rnd.sample(sorted(rows), min(VERIFY_N, len(rows)))
    bad = 0
    for d, loc in sample:
        status, text, _ = fetch(loc)
        m = (PUB.search(text) or META.search(text)) if status == 200 and text else None
        if not m:
            print(f"  verify: {loc[:70]} -> HTTP {status}, no datePublished")
            bad += 1
            continue
        pub = m.group(1)  # e.g. 2026-09-26T02:39:00Z == lastmod 2026-09-25T21:39-05:00
        # convert UTC to site-local -05:00 date for comparison
        from datetime import datetime, timedelta, timezone
        local = datetime.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc) - timedelta(hours=5)
        if abs((local.date() - datetime.strptime(d, "%Y-%m-%d").date()).days) > 1:
            print(f"  verify MISMATCH: listed {d}, page {pub} -> {loc[:70]}")
            bad += 1
    print(f"spot check: {VERIFY_N} sampled, {bad} page dates >1 day off listed date")

    rows = sorted(dict.fromkeys(rows))  # unique (date,url), sorted
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for d, loc in rows:
            f.write(f"{loc}\t{d}\n")
    print(f"wrote {len(rows)} URLs to {OUT}")
    for day in sorted(per_day):
        print(f"  {day}: {per_day[day]}")
    missing = [d for d in per_day if per_day[d] < 15]
    print("days under 15 URLs:", missing if missing else "none")


if __name__ == "__main__":
    main()
