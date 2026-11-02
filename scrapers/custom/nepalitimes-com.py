#!/usr/bin/env python3
"""Nepali Times (nepalitimes.com) — article URLs published 2026-09-25 .. 2026-10-25.

Route (all through scapars.polite_fetch, robots permissive "User-Agent: * / Disallow:"):
  1. robots.txt names https://media.nepalitimes.com/sitemap/sitemap_index.xml
  2. the index lists articles-1.xml (flat urlset, 20 000 <loc>/<lastmod> pairs, recent first),
     articles-2.xml and news.xml — no recursion needed
  3. for every <loc> whose <lastmod> falls near the window, fetch the article page and take the
     date from its JSON-LD "datePublished" (Asia/Kathmandu, +05:45) as the authoritative publish
     date; the sitemap <lastmod> is the same instant in UTC for recent posts, so it is only used
     to pre-filter and as a fallback.
  4. keep only URLs whose page yields >= 1500 characters of body text (so a re-fetch of any listed
     URL shows real article text), date inside the window, one row per URL.

Nepali Times is a weekly magazine that also posts online: ~2-5 articles/day, so no single day
reaches 15. Counts per day are printed at the end.
"""
import collections
import datetime
import html
import json
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = "2026-09-25"
END = "2026-10-25"
INDEX = "https://media.nepalitimes.com/sitemap/sitemap_index.xml"
SKIP_MAPS = ("tags.xml", "pages.xml")
OUT = "data/urls_custom/nepalitimes-com.tsv"
MIN_TEXT = 1500


def get(url, tries=3):
    for i in range(tries):
        try:
            status, body, _ = fetch(url)
        except Exception as exc:  # network hiccup: retry
            print("  ! %s %s" % (type(exc).__name__, url[:80]), file=sys.stderr)
            status, body = 0, None
        if status == 200 and body:
            return body
        print("  ! HTTP %s %s (try %d)" % (status, url[:80], i + 1), file=sys.stderr)
        time.sleep(2 * (i + 1))
    return None


def strip_text(page):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return html.unescape(re.sub(r"\s+", " ", body)).strip()


def page_date(page):
    """Publish date as the page states it: JSON-LD datePublished, else <time datetime>."""
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                dp = node.get("datePublished")
                if isinstance(dp, str) and re.match(r"\d{4}-\d{2}-\d{2}", dp):
                    return dp[:10], "jsonld"
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', page)
    if m:
        return m.group(1), "time"
    return None, ""


def in_window(d):
    return START <= d <= END


def main():
    global START, END
    if len(sys.argv) > 2 and re.match(r"\d{4}-\d{2}-\d{2}$", sys.argv[1]):
        START, END = sys.argv[1], sys.argv[2]
    lo = (datetime.date.fromisoformat(START) - datetime.timedelta(days=1)).isoformat()
    hi = (datetime.date.fromisoformat(END) + datetime.timedelta(days=1)).isoformat()

    idx = get(INDEX)
    if not idx:
        print("FATAL: sitemap index unreachable", file=sys.stderr)
        return 1
    maps = [u for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx) if not u.endswith(SKIP_MAPS)]
    print("sitemap index: %d urlsets" % len(maps))

    cands = {}  # url -> sitemap lastmod date (UTC instant)
    for sm in maps:
        body = get(sm)
        if not body:
            continue
        pairs = re.findall(r"<loc>\s*(.*?)\s*</loc>\s*<lastmod>\s*(.*?)\s*</lastmod>", body)
        if not pairs:
            pairs = [(u, "") for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", body)]
        kept = 0
        for loc, lm in pairs:
            loc = html.unescape(loc)
            d = lm[:10]
            if d and (d < lo or d > hi):
                continue
            if "/category/" in loc or "/tag/" in loc:
                continue
            cands.setdefault(loc, d)
            kept += 1
        print("  %s: %d urls, %d near window" % (sm.rsplit("/", 1)[-1], len(pairs), kept))

    print("candidates: %d — verifying page dates and text" % len(cands))
    rows = []
    stats = collections.Counter()
    for i, (url, sdate) in enumerate(sorted(cands.items())):
        page = get(url, tries=2)
        if page is None:
            stats["fetch_failed"] += 1
            continue
        pdate, src = page_date(page)
        text = strip_text(page)
        if not pdate:
            pdate = sdate
            src = "lastmod"
        if not pdate or not in_window(pdate):
            stats["date_outside_" + (pdate or "none")] += 1
            continue
        if sdate and abs((datetime.date.fromisoformat(pdate) -
                          datetime.date.fromisoformat(sdate)).days) > 1:
            stats["date_mismatch"] += 1
            continue
        if len(text) < MIN_TEXT:
            stats["short_text"] += 1
            continue
        rows.append((pdate, url, src, len(text)))
        if (i + 1) % 25 == 0:
            print("  ...%d/%d checked" % (i + 1, len(cands)))

    rows.sort(key=lambda r: (r[0], r[1]))
    seen, out = set(), []
    for d, url, src, n in rows:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, d))

    OUT_DIR = OUT.rsplit("/", 1)[0]
    import os
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, d in out:
            f.write("%s\t%s\n" % (url, d))
    os.replace(tmp, OUT)

    per_day = collections.Counter(d for _, d in out)
    print("wrote %d unique URLs to %s" % (len(out), OUT))
    span = (datetime.date.fromisoformat(END) - datetime.date.fromisoformat(START)).days
    for k in range(span + 1):
        d = (datetime.date.fromisoformat(START) + datetime.timedelta(days=k)).isoformat()
        print("  %s  %d" % (d, per_day.get(d, 0)))
    print("dropped: " + ", ".join("%s=%d" % kv for kv in sorted(stats.items())))
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("CHECK DAY %s: %d" % (d, per_day.get(d, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
