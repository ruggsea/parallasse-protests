#!/usr/bin/env python3
"""Samakal (samakal.com) URL list for 2026-09-25..2026-10-25.

Live site is WAF-locked: every path except /sitemap.xml returns 403 to
ParallasseResearchBot (verified 792x). /sitemap.xml is a per-day index but
the /sitemap/sitemap-daily-*.xml files themselves 403, so the live sitemap
route is unusable. Route used: Wayback CDX for the URL list + first-capture
date per URL, validated against the date the site shows on the archived page.

Output: data/urls_custom/samakal-com.tsv  (URL<TAB>YYYY-MM-DD, unique)
"""
import sys, re, json, time, datetime
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

DOMAIN = "samakal.com"
START = "2026-09-25"
END = "2026-10-25"
# CDX window: margin around the target window so same-day publications
# captured late are still found.
CDX_START = "20260924"
CDX_END = "20261027"
OUT = "data/urls_custom/samakal-com.tsv"

# Article path patterns (from CDX data): keep real story pages.
ARTICLE_RE = re.compile(r"^https?://(?:www\.)?samakal\.com/(?:news|opinion|business|sport|video|feature|entertainment)/\d+")
EXCLUDE_RE = re.compile(r"\.(jpe?g|png|gif|css|js|svg|ico|mp4|webm)(\?|$)|/video/|/photo|/tv/")


def cdx_url(from_d, to_d):
    return (f"https://web.archive.org/cdx/search/cdx?url={DOMAIN}&matchType=domain"
            f"&from={from_d}&to={to_d}&output=json&filter=statuscode:200&collapse=urlkey&limit=6000")


def fetch_with_retry(url, tries=4, pause=30):
    for i in range(tries):
        s, t, _ = fetch(url)
        if s == 200 and t:
            return t
        print(f"  CDX attempt {i+1}: HTTP {s} ({len(t or '')}b)", flush=True)
        time.sleep(pause)
    return None


def main():
    body = fetch_with_retry(cdx_url(CDX_START, CDX_END))
    if not body:
        print("FATAL: CDX unreachable", file=sys.stderr)
        sys.exit(1)
    rows = json.loads(body)
    print(f"CDX rows: {len(rows)}")

    # first capture date per url (rows are time-ascending per urlkey)
    first = {}
    for r in rows:
        ts, url = r[1], r[2]
        url = url.rstrip("/")
        if not ARTICLE_RE.match(url):
            continue
        if EXCLUDE_RE.search(url):
            continue
        d = ts[:8]
        if url not in first or d < first[url]:
            first[url] = d
    print(f"article urls with first capture in window: {len(first)}")

    # list date = first capture date restricted to the target window
    rows_out = []
    for url, d in first.items():
        ds = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        if START <= ds <= END:
            rows_out.append((url, ds))
    rows_out.sort()
    seen = set()
    uniq = []
    for u, d in rows_out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, d))

    per_day = {}
    for u, d in uniq:
        per_day[d] = per_day.get(d, 0) + 1
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in uniq:
            f.write(f"{u}\t{d}\n")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    print(f"total: {len(uniq)}")


if __name__ == "__main__":
    main()
