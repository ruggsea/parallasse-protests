#!/usr/bin/env python3
"""Scrape Deutschlandfunk (deutschlandfunk.de) article URLs for 2026-09-25..2026-10-25.

Route: robots.txt names 12 Google-News sitemaps (per section filter), each carrying
<news:publication_date> on every entry. Union of all sitemaps covers the window.
Listed date = local date part of news:publication_date (== page JSON-LD datePublished).
"""
import re
import sys
from collections import defaultdict
from datetime import datetime, date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.deutschlandfunk.de"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/deutschlandfunk-de.tsv"

NS_NEWS = "{http://www.google.com/schemas/sitemap-news/0.9}"


def parse_dt(s):
    # 2026-10-26T07:50:00.000+01:00 or plain lastmod 2026-10-26T07:50:00Z
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def main():
    s, t, _ = fetch(BASE + "/robots.txt")
    assert s == 200 and t, f"robots.txt fetch failed: {s}"
    smaps = re.findall(r"^sitemap:\s*(\S+)", t, re.M)
    print(f"robots.txt: {len(smaps)} sitemaps")

    urls = {}  # url -> (date, source)
    for sm in smaps:
        s, t, _ = fetch(sm)
        if s != 200 or not t:
            print(f"  {sm}: HTTP {s}")
            continue
        blocks = re.findall(r"<url>.*?</url>", t, re.S)
        n_win = 0
        for b in blocks:
            m = re.search(r"<loc>\s*(.*?)\s*</loc>", b)
            if not m:
                continue
            u = m.group(1).strip()
            if u.startswith("/"):
                u = BASE + u
            # keep article pages only
            if not re.search(r"\.html$", u):
                continue
            d = None
            src = ""
            m = re.search(r"<news:publication_date>\s*(.*?)\s*</news:publication_date>", b)
            if m:
                d = parse_dt(m.group(1))
                src = "news:publication_date"
            if d is None:
                m = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", b)
                if m:
                    d = parse_dt(m.group(1))
                    src = "lastmod"
            if d is None or d < START or d > END:
                continue
            n_win += 1
            prev = urls.get(u)
            # prefer earliest date (publication, not edit) and prefer news:publication_date
            if prev is None or (d, 0 if src.startswith("news") else 1) < (prev[0], 0 if prev[1].startswith("news") else 1):
                urls[u] = (d, src)
        print(f"  {sm.split('/')[-1]}: HTTP {s}, {len(blocks)} urls, {n_win} in window")

    byday = defaultdict(int)
    for u, (d, _) in urls.items():
        byday[d] += 1

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u in sorted(urls):
            d, _ = urls[u]
            f.write(f"{u}\t{d.isoformat()}\n")

    print(f"WROTE {len(urls)} urls to {OUT}")
    for d in sorted(byday):
        print(f"  {d}: {byday[d]}")
    missing = [d for d in (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)) if byday[d] < 15]
    if missing:
        print("LOW DAYS:", ", ".join(str(d) for d in missing))


if __name__ == "__main__":
    main()
