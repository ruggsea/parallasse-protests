#!/usr/bin/env python3
"""List observador.pt article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, permissive for our UA) names https://observador.pt/wp-sitemap.xml,
a WordPress core sitemap index with 244 numbered post sitemaps (wp-sitemap-posts-post-N.xml,
2000 URLs each, ordered by <lastmod> ASCENDING, oldest post first). The sitemaps are the only
working route: the WP REST API (/wp-json) returns 404 and ?rest_route= 404.

Observador permalinks embed the publication date: https://observador.pt/YYYY/MM/DD/slug/.
The datePublished in each article's JSON-LD was verified to match the URL date exactly
(3 spot checks: 2026-09-30, 2026-10-10, 2026-10-20). <lastmod> is the EDIT time (one sample
had dateModified 5h after datePublished), so it is used ONLY to locate the sitemaps that
cover the window, never as the listed date.

The script binary-searches the post sitemaps for the ones whose lastmod range intersects the
window (with a +/-7d margin, so articles published in-window and edited shortly after are
still found even on a later re-run), extracts every URL whose path date is inside the window,
dedupes and writes data/urls_custom/observador-pt.tsv (URL<TAB>YYYY-MM-DD, sorted).
"""
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/observador-pt.tsv"
BASE = "https://observador.pt"
WIN_START, WIN_END = "2026-09-25", "2026-10-25"
MARGIN_START, MARGIN_END = "2026-09-18", "2026-11-01"
URL_RE = re.compile(r"^" + BASE + r"/(\d{4})/(\d{2})/(\d{2})/")


def get_lastmod_range(url):
    """Return (min_lastmod, max_lastmod) of a sitemap, or (None, None) on failure."""
    last = None
    for attempt in range(3):
        status, text, _ = fetch(url)
        if status == 200 and text:
            lm = re.findall(r"<lastmod>([^<]+)</lastmod>", text)
            return (lm[0], lm[-1]) if lm else (None, None)
        time.sleep(2 + 2 * attempt)
    return (None, None)


def post_sitemap_numbers():
    status, text, _ = fetch(BASE + "/wp-sitemap.xml")
    if status != 200:
        raise SystemExit(f"sitemap index failed: HTTP {status}")
    locs = re.findall(r"<loc>([^<]+)</loc>", text)
    nums = sorted(
        int(m.group(1))
        for l in locs
        if (m := re.search(r"wp-sitemap-posts-post-(\d+)\.xml$", l))
    )
    return nums


def find_covering_sitemaps(nums):
    """Sitemaps ordered by lastmod ascending; return numbers whose lastmod range
    intersects [MARGIN_START, MARGIN_END] (binary search + linear confirmation)."""
    # find first sitemap with max_lastmod >= MARGIN_START
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        _, mx = get_lastmod_range(f"{BASE}/wp-sitemap-posts-post-{nums[mid]}.xml")
        if mx is None or mx[:10] < MARGIN_START:
            lo = mid + 1
        else:
            hi = mid
    start_i = lo
    # walk forward until min_lastmod > MARGIN_END
    covering = []
    i = start_i
    while i < len(nums):
        mn, mx = get_lastmod_range(f"{BASE}/wp-sitemap-posts-post-{nums[i]}.xml")
        if mn is None:
            i += 1
            continue
        covering.append(nums[i])
        if mn[:10] > MARGIN_END:
            break
        i += 1
    return covering


def main():
    nums = post_sitemap_numbers()
    print(f"post sitemaps: {len(nums)} (1..{nums[-1]})")
    covering = find_covering_sitemaps(nums)
    print(f"covering sitemaps (lastmod intersects {MARGIN_START}..{MARGIN_END}): {covering}")

    found = {}
    for n in covering:
        url = f"{BASE}/wp-sitemap-posts-post-{n}.xml"
        status, text, _ = fetch(url)
        if status != 200:
            print(f"WARN: {url} -> HTTP {status}, skipping", file=sys.stderr)
            continue
        for loc in re.findall(r"<loc>([^<]+)</loc>", text):
            m = URL_RE.match(loc)
            if not m:
                continue
            d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if WIN_START <= d <= WIN_END:
                found.setdefault(loc, d)

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url, d in rows:
            f.write(f"{url}\t{d}\n")

    counts = Counter(d for _, d in rows)
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    print("per-day counts:")
    for d in sorted(counts):
        print(f"  {d}: {counts[d]}")
    missing = [d for d in (WIN_START, "2026-09-30", "2026-10-10", "2026-10-20", WIN_END)
               if counts.get(d, 0) < 15]
    if missing:
        print(f"WARN: fewer than 15 URLs on: {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
