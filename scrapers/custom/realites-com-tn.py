#!/usr/bin/env python3
"""realites.com.tn (Realites, Tunisia) - list article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
  robots.txt is permissive (Yoast block, only /fr/wp-admin/ disallowed) and names two
  sitemap indexes: /fr/sitemap_index.xml and /ar/sitemap_index.xml (French + Arabic site).
  Each index lists post-sitemap.xml, post-sitemap2.xml, ... post-sitemapN.xml where the
  UNNUMBERED file is the OLDEST (2012) and the highest number is the newest file
  (fr: post-sitemap109.xml = 2026-09-13..2026-10-25, 569 urls; ar: post-sitemap20.xml,
  2026-06-22..now, 905 urls).
  So: for each language walk files backwards from the newest until the oldest <lastmod>
  in a file is <= window start; that fully covers the window (1 request per language).
  Listed date = date-part of <lastmod> (UTC), which equals the page's own
  datePublished/meta article:published_time date-part (both shown +00:00 first; verified
  on fr and ar samples: e.g. lastmod 2026-09-30T05:03:50+00:00 vs page datePublished
  2026-09-30T05:02:05+00:00; lastmod 2026-10-20T08:14:06+00:00 vs datePublished
  2026-10-20T08:14:06+00:00; ar lastmod 2026-10-10T09:32:32+00:00 vs page
  2026-10-10T09:31:14+00:00). fr alone has 14/14/13 on 09-30/10-10/10-20, below the 15
  bar, so the /ar/ URLs are included too (different URLs, same outlet) -> 23/22/21.
"""
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://realites.com.tn"
START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/realites-com-tn.tsv"


def get(url):
    """fetch() with retries: status 0 (transport error) or 429/5xx -> back off."""
    for attempt in range(5):
        s, t, _ = fetch(url)
        if s == 200 and t:
            return s, t
        print(f"retry {attempt + 1} for {url}: status {s}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    return s, t


def post_files(lang):
    """Return the language's post-sitemap URLs sorted oldest-file -> newest-file."""
    s, t = get(f"{BASE}/{lang}/sitemap_index.xml")
    if s != 200 or not t:
        print(f"index {lang}: status {s}", file=sys.stderr)
        return []
    locs = re.findall(r"<loc>(.*?)</loc>", t)

    def num(loc):
        m = re.search(r"post-sitemap(\d*)\.xml$", loc)
        return int(m.group(1) or 1)  # unnumbered file = 1 = oldest

    files = [l for l in locs if re.search(r"post-sitemap\d*\.xml$", l)]
    return sorted(files, key=num)


def file_entries(lang, n):
    """Return [(url, lastmod), ...] of one post-sitemap file."""
    name = f"post-sitemap{n}.xml" if n > 1 else "post-sitemap.xml"
    s, t = get(f"{BASE}/{lang}/{name}")
    if s != 200 or not t:
        print(f"{lang}/{name}: status {s}", file=sys.stderr)
        return []
    locs = re.findall(r"<loc>(.*?)</loc>", t)
    mods = re.findall(r"<lastmod>(.*?)</lastmod>", t)
    return list(zip(locs, mods))


def main():
    rows = {}  # url -> listed date (UTC date-part of sitemap lastmod)
    for lang in ("fr", "ar"):
        files = post_files(lang)
        if not files:
            continue

        def num(loc):
            m = re.search(r"post-sitemap(\d*)\.xml$", loc)
            return int(m.group(1) or 1)

        n = num(files[-1])  # newest file
        while n >= 1:
            entries = file_entries(lang, n)
            if not entries:
                break
            oldest = min(m for _, m in entries)[:10]
            for u, m in entries:
                d = m[:10]
                if START <= d <= END:
                    rows.setdefault(u, d)
            if oldest <= START or n == 1:
                break
            n -= 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for u in sorted(rows):
            f.write(f"{u}\t{rows[u]}\n")

    per_day = Counter(rows.values())
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")


if __name__ == "__main__":
    main()
