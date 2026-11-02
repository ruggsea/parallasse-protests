#!/usr/bin/env python3
"""La Razón (Peru) - larazon.pe

Route: robots.txt is permissive and advertises https://larazon.pe/sitemap_index.xml.
That index is a Yoast sitemapindex listing numbered post sitemaps
(post-sitemap.xml, post-sitemap100.xml, post-sitemap101.xml, ...).  The newest
numbered file holds ~800-1000 posts spread over ~5 weeks, so the 31-day window
usually fits in ONE file and never needs more than a couple.

Listed date = the date part of <lastmod> in that post sitemap, which is the post
publication time (UTC, minutes granularity).  Verified against the page's own
JSON-LD datePublished on samples.

What does NOT work here:
  * https://larazon.pe/sitemap.xml  -> 403 (only sitemap_index.xml exists)
  * /wp-json/wp/v2/posts            -> 401 (REST API disabled for anonymous)
  * /feed/                          -> serves the HTML homepage, not a feed
  * Wayback CDX                     -> timeouts/504
"""

import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://larazon.pe"
INDEX = BASE + "/sitemap_index.xml"
OUT = "data/urls_custom/larazon-pe.tsv"

START = "2026-09-25"
END = "2026-10-25"

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
LASTMOD_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S)
ENTRY_RE = re.compile(r"<url>(.*?)</url>", re.S)
SM_RE = re.compile(r"<sitemap>(.*?)</sitemap>", re.S)

SKIP_PATH = re.compile(
    r"/(blog|category|categoria|tag|author|page|wp-content|wp-json|feed)/"
    r"|/wp-content/|\.(jpg|jpeg|png|gif|webp|pdf|xml|json)$",
    re.I,
)


def sitemap_entries(xml):
    """Yield (loc, lastmod) for each <url> entry of a flat urlset."""
    for block in ENTRY_RE.findall(xml):
        m = LOC_RE.search(block)
        if not m:
            continue
        loc = m.group(1).strip()
        lm = LASTMOD_RE.search(block)
        yield loc, (lm.group(1).strip() if lm else "")


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {url} exception {type(exc).__name__}: {exc}", flush=True)
            status, text = None, None
        if status == 200 and text:
            return text
        print(f"  ! {url} -> {status} (try {i + 1}/{tries})", flush=True)
        time.sleep(3 * (i + 1))
    return None


def main():
    html = get(INDEX)
    if not html:
        print("FATAL: sitemap index unreachable")
        return 1

    numbered, plain = [], []
    for block in SM_RE.findall(html):
        m = LOC_RE.search(block)
        if not m:
            continue
        loc = m.group(1).strip()
        if not re.search(r"/post-sitemap\d*\.xml$", loc):
            continue  # pages, categories, tags, print editions
        lm = LASTMOD_RE.search(block)
        lm = lm.group(1).strip() if lm else ""
        (numbered if re.search(r"/post-sitemap\d+\.xml$", loc) else plain).append((loc, lm))

    # Yoast fills post-sitemap.xml with the oldest content and keeps appending
    # numbered files, so the window lives in a numbered file.  The bare file is
    # only a fallback (it also carries non-post URLs such as /blog/).
    cands = numbered or plain

    # A file can contain window posts only if its newest entry (index lastmod)
    # is not older than the window start.  Newest first, keep a few.
    cands = [c for c in cands if c[1][:10] >= START]
    cands.sort(key=lambda c: c[1], reverse=True)
    print(f"post sitemaps that may reach the window: {len(cands)}", flush=True)
    for loc, lm in cands[:6]:
        print(f"  {loc} newest={lm}", flush=True)

    rows = {}
    for loc, lm in cands[:5]:
        xml = get(loc)
        if not xml:
            continue
        n_win = 0
        oldest = None
        for url, lastmod in sitemap_entries(xml):
            if not lastmod:
                continue
            day = lastmod[:10]
            if oldest is None or day < oldest:
                oldest = day
            if not (START <= day <= END):
                continue
            if SKIP_PATH.search(url):
                continue
            url = url.split("?")[0].split("#")[0]
            if not url.startswith(BASE):
                continue
            n_win += 1
            # keep the earliest lastmod date for a URL seen twice
            if url not in rows or day < rows[url]:
                rows[url] = day
        print(f"  {loc}: {n_win} in-window (oldest entry {oldest})", flush=True)
        # stop early once we have walked past the window start
        if oldest and oldest < START and n_win:
            continue

    if not rows:
        print("FATAL: no in-window URLs found")
        return 1

    lines = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for url, day in lines:
            fh.write(f"{url}\t{day}\n")

    counts = Counter(day for _, day in lines)
    print(f"wrote {len(lines)} URLs to {OUT}", flush=True)
    for day in sorted(counts):
        print(f"  {day}\t{counts[day]}", flush=True)
    days_with = len(counts)
    print(f"days covered: {days_with}", flush=True)
    for day in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"check day {day}: {counts.get(day, 0)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
