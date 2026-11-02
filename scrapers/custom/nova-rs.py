#!/usr/bin/env python3
"""Nova (Serbia, nova.rs): list article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, permissive: only /admin/ and /api/v1/* disallowed) names
sitemap.xml, a sitemapindex of ~630 files. The sitemap_post_N.xml files are
strictly ordered by lastmod DESCENDING, 1000 URLs each, ~5.5 days per file, so
the first few cover the whole window.

Date: <lastmod> in the post sitemaps IS the publication time, not an edit time.
Verified on 4 articles spanning two files: lastmod matched the page JSON-LD
datePublished to the second (e.g. sitemap 2026-10-20T23:04:42+02:00 vs page
2026-10-20T21:04:42.360428+00:00; another: 07:31:16+01:00 vs 06:31:16.587618+00:00,
where dateModified was already 6 min later). We list the lastmod date in UTC so
it equals the page JSON-LD datePublished date exactly.

The news sitemap (sitemap_news_1.xml, has news:publication_date) only reaches
back ~2 days, so it cannot cover the window; the post sitemaps are used instead.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

OUT_DIR = Path("data/urls_custom")
OUT_FILE = OUT_DIR / "nova-rs.tsv"
START = "2026-09-25"
END = "2026-10-25"
BASE = "https://nova.rs"


def parse_ts(s):
    """lastmod like 2026-10-20T23:04:42+02:00 -> aware datetime."""
    return datetime.fromisoformat(s)


def main():
    # 1. sitemap index -> ordered list of post sitemaps
    status, text, _ = fetch(BASE + "/sitemap.xml")
    if status != 200:
        sys.exit(f"sitemap.xml gave {status}")
    nums = sorted({int(m) for m in re.findall(r"sitemap_post_(\d+)\.xml", text)})
    if not nums:
        sys.exit("no sitemap_post_N.xml entries in index")
    print(f"index: {len(nums)} post sitemaps (1..{nums[-1]})")

    urls = {}  # url -> UTC date str
    for n in nums:
        status, text, _ = fetch(f"{BASE}/sitemap/sitemap_post_{n}.xml")
        if status != 200:
            print(f"  post_{n}: HTTP {status}, skipping")
            continue
        pairs = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text)
        if not pairs:
            print(f"  post_{n}: no urls, stopping")
            break
        newest = max(parse_ts(lm) for _, lm in pairs)
        oldest = min(parse_ts(lm) for _, lm in pairs)
        n_in = 0
        for loc, lm in pairs:
            dt = parse_ts(lm).astimezone(timezone.utc)
            d = dt.date().isoformat()
            if START <= d <= END:
                if loc not in urls:
                    urls[loc] = d
                n_in += 1
        print(f"  post_{n}: {len(pairs)} urls {oldest.date()}..{newest.date()}, {n_in} in window")
        if newest.date().isoformat() < START:
            # files are descending by lastmod; this one is fully older than the window
            break

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = sorted(urls.items())
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for url, d in lines:
            f.write(f"{url}\t{d}\n")

    per_day = {}
    for _, d in lines:
        per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    print(f"wrote {len(lines)} unique URLs to {OUT_FILE}")


if __name__ == "__main__":
    main()
