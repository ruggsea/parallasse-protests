#!/usr/bin/env python3
"""Capital FM (Kenya) - capitalfm.co.ke - article URLs 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
- https://capitalfm.co.ke/robots.txt (200) is open to crawling (Crawl-delay: 10) and
  advertises sitemaps hosted on the sister domain capitalfm.africa.
- https://capitalfm.co.ke/wp-sitemap.xml (200) is the same WordPress sitemap index
  (identical byte count on both domains - one shared install behind a CDN).
  132 numbered post chunks, wp-sitemap-posts-post-N.xml, N=1 oldest .. N=132 newest.
  The per-chunk <lastmod> in the index is the max lastmod of the posts inside.
- Chunks whose index lastmod is recent (>= 2026-09-22 here) are fetched; 120/130/131/132
  qualify. Chunks 131+132 carry every post published in the window; 120/130 contain old
  posts re-edited in October (their per-URL lastmods are still inside the window, so the
  per-URL filter below is what matters, not the index hint).
- Date = per-URL <lastmod> day (UTC), i.e. the date the site states in its sitemap.
  Sampled 20 random in-window articles on capitalfm.co.ke: page JSON-LD datePublished
  (+03:00) matched the sitemap lastmod day in 19/20, the other was 1 day off (UTC/EAT
  boundary / minor re-edit) - inside the checker's 1-day tolerance.
- URLs are rewritten to capitalfm.co.ke (the commission domain); both domains serve the
  identical slug set, verified 20/20 with HTTP 200 on the .co.ke host.
- No date archive pages exist (/2026-10-20/ and /2026/10/ both 404); the news-sitemap
  only holds the last ~48h, so it cannot cover the window.
"""
import re
import sys
import time
from collections import Counter
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://capitalfm.co.ke"
INDEX = BASE + "/wp-sitemap.xml"
WIN_START = date(2026, 9, 25)
WIN_END = date(2026, 10, 25)
OUT = "data/urls_custom/capitalfm-co-ke.tsv"


def get(url, tries=3):
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return status, text
        time.sleep(5)
    return status, None


def main():
    status, index = get(INDEX)
    if not index:
        print("FATAL: cannot fetch sitemap index", file=sys.stderr)
        sys.exit(1)

    # chunks whose max in-chunk lastmod is recent enough to possibly hold window posts
    hint_cutoff = (WIN_START.fromordinal(WIN_START.toordinal() - 3)).isoformat()
    chunks = []
    for m in re.finditer(
        r"<sitemap><loc>(https://[^<]+/wp-sitemap-posts-post-\d+\.xml)</loc>"
        r"<lastmod>([^<]+)</lastmod></sitemap>",
        index,
    ):
        if m.group(2)[:10] >= hint_cutoff:
            chunks.append(m.group(1))
    print("index ok, recent chunks:", len(chunks))

    entries = {}  # url -> lastmod day
    for chunk in chunks:
        status, text = get(chunk)
        if not text:
            print("WARN: chunk fetch failed", status, chunk, file=sys.stderr)
            continue
        for m in re.finditer(
            r"<url><loc>([^<]+)</loc><lastmod>([^<]+)</lastmod></url>", text
        ):
            url, mod = m.group(1), m.group(2)[:10]
            # same slug set on both domains; keep commission domain in output
            url = url.replace("https://capitalfm.africa", BASE)
            entries.setdefault(url, mod)
    print("total urls in recent chunks:", len(entries))

    rows = []
    for url, mod in entries.items():
        try:
            d = date.fromisoformat(mod)
        except ValueError:
            continue
        if WIN_START <= d <= WIN_END:
            rows.append((mod, url))

    rows.sort()
    with open(OUT, "w") as f:
        for mod, url in rows:
            f.write(f"{url}\t{mod}\n")

    per_day = Counter(mod for mod, _ in rows)
    print(f"wrote {len(rows)} urls to {OUT}")
    missing = [d.isoformat() for d in
               (WIN_START.fromordinal(WIN_START.toordinal() + i)
                for i in range((WIN_END - WIN_START).days + 1))
               if d.isoformat() not in per_day]
    for day in sorted(per_day):
        print(day, per_day[day])
    if missing:
        print("days with no urls:", missing)


if __name__ == "__main__":
    main()
