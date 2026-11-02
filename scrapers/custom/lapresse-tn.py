#!/usr/bin/env python3
"""La Presse de Tunisie (lapresse.tn) — article URLs published 2026-09-25..2026-10-25.

Route: WordPress + Yoast. robots.txt (200, permissive: only /wp-admin/, /*?s= and
/wp-content/boost-cache/ disallowed) advertises https://www.lapresse.tn/sitemap_index.xml.
The index lists post-sitemap.xml, post-sitemap2.xml ... post-sitemap42.xml, one flat urlset
per ~1000 posts, NEWEST NUMBER = NEWEST POSTS (post-sitemap42 lastmod 2026-10-27,
post-sitemap41 lastmod 2026-10-14, post-sitemap40 lastmod 2026-09-28, post-sitemap39
lastmod 2026-09-13).  So the window lives in 40/41/42 and we pick children by lastmod
rather than hard-coding numbers.

Date: every post URL is /YYYY/MM/DD/slug/ and that date segment equals the page's
JSON-LD "datePublished" and <meta property="article:published_time"> (UTC, verified on 5
pages across 2026-09-30, 2026-10-10, 2026-10-20 — exact match, e.g.
2026-10-10T17:29:48+00:00).  <lastmod> is the *modified* stamp (drifts a day or more), so
it is only used as a fallback for the rare URL without a dated path.

Output: data/urls_custom/lapresse-tn.tsv  (URL<TAB>YYYY-MM-DD, no header, unique URLs).
"""
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/lapresse-tn.tsv")
SITEMAP_INDEX = "https://www.lapresse.tn/sitemap_index.xml"
START = "2026-09-25"
END = "2026-10-25"

DAY_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
URL_RE = re.compile(r"<url>\s*<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?", re.S)
FAILED = []


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as e:  # noqa: BLE001
            status, text = 0, None
            print(f"  error {url}: {e}", file=sys.stderr)
        if status == 200 and text:
            return text
        if status in (-1, 404, 410):
            break
        time.sleep(3 * (i + 1))
    FAILED.append((url, status))
    return None


def post_sitemaps():
    """Children of the index that can hold posts published inside the window."""
    text = get(SITEMAP_INDEX)
    if not text:
        # last resort: the three files we know hold the window
        return [f"https://www.lapresse.tn/post-sitemap{n}.xml" for n in (40, 41, 42)]
    kids = re.findall(
        r"<sitemap>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S)
    posts = [(loc, lm[:10]) for loc, lm in kids if "post-sitemap" in loc]
    chosen = [loc for loc, lm in posts
              if lm >= "2026-09-20" or loc.endswith("post-sitemap.xml")]
    # newest (highest number) always counts, whatever the index says
    if posts:
        newest = max(posts, key=lambda p: int(re.search(r"post-sitemap(\d*)\.xml$",
                                                        p[0]).group(1) or 1))
        if newest[0] not in chosen:
            chosen.append(newest[0])
    return chosen


def main():
    t0 = time.time()
    urls = {}
    for sm in post_sitemaps():
        text = get(sm)
        if not text:
            print(f"  sitemap FAILED: {sm}")
            continue
        n = 0
        for loc, lastmod in URL_RE.findall(text):
            n += 1
            m = DAY_RE.search(loc)
            if m:
                day = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            elif lastmod:
                day = lastmod[:10]
            else:
                continue
            if START <= day <= END:
                urls[loc.strip()] = day
        print(f"  {sm.rsplit('/', 1)[-1]}: {n} <loc>, {len(urls)} in window so far")

    rows = sorted(urls.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")
    os.replace(tmp, OUT)

    per_day = Counter(d for _, d in rows)
    print(f"\nwrote {len(rows)} unique URLs to {OUT}")
    for day in sorted(per_day):
        print(f"  {day}\t{per_day[day]}")
    for day in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"  check day {day}: {per_day.get(day, 0)}")
    print(f"days covered: {len(per_day)}/31  in {time.time() - t0:.1f}s")
    if FAILED:
        print("FAILED fetches:", FAILED)


if __name__ == "__main__":
    main()
