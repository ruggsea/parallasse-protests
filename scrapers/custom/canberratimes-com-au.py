#!/usr/bin/env python3
"""The Canberra Times (canberratimes.com.au): articles published 2026-09-25..2026-10-25.

Route: robots.txt (200) points at sitemap.xml, an index of per-DAY news
sitemaps sitemap-YYYYMMDD.xml, one per publication day. Each per-day urlset
lists the articles published that day with a per-URL <lastmod> (date only),
the site-provided date; we list each URL under its lastmod date (equals the
page datePublished, AEST local; matches page dateModified within 1 day UTC).
Buckets are disjoint (647 unique URLs).
"""
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://www.canberratimes.com.au"
START, END = date(2026, 9, 25), date(2026, 10, 25)
OUT = Path(__file__).resolve().parents[2] / "data" / "urls_custom" / "canberratimes-com-au.tsv"


def get(url, tries=3):
    status, text, _ = fetch(url)
    for i in range(tries):
        if status == 200 and text:
            return status, text
        time.sleep(5 * (i + 1))
        status, text, _ = fetch(url)
    return status, text


def main():
    by_url = {}
    d = START
    while d <= END:
        url = f"{BASE}/sitemap-{d:%Y%m%d}.xml"
        status, text = get(url)
        if status != 200 or not text:
            sys.exit(f"failed to fetch {url}: status {status}")
        pairs = re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text)
        if not pairs:
            sys.exit(f"no URLs parsed from {url}")
        for loc, lm in pairs:
            loc, lm = loc.strip(), lm.strip()[:10]
            if not (START.isoformat() <= lm <= END.isoformat()):
                lm = d.isoformat()  # fallback: the day's sitemap bucket
            prev = by_url.get(loc)
            if prev is None or lm > prev:
                by_url[loc] = lm
        print(f"{d:%Y-%m-%d}: fetched {len(pairs)} URLs from per-day sitemap", flush=True)
        d += timedelta(days=1)

    rows = sorted((lm, u) for u, lm in by_url.items())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for lm, u in rows:
            f.write(f"{u}\t{lm}\n")
    counts = Counter(lm for lm, _ in rows)
    for day in sorted(counts):
        print(f"{day}: {counts[day]}")
    print(f"total: {len(rows)} URLs written to {OUT}")


if __name__ == "__main__":
    main()
