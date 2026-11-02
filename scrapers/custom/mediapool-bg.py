#!/usr/bin/env python3
"""List mediapool.bg article URLs published 2026-09-25..2026-10-25.

Primary route: the site's own WordPress REST API
  /wp-json/wp/v2/posts?after=...&before=...&_fields=date,date_gmt,link
`date` is the site-local publication datetime, the same value the article
page exposes in <meta article:published_time>; trafilatura extracts it as the
page date, so listed date == page date.
Fallback route (if the REST API is unreachable): post-sitemap1..3.xml
<lastmod> (allowed per brief) merged with news-sitemap.xml
news:publication_date (which wins when both cover a URL).
Every request goes through polite_fetch.fetch.
"""
import json
import re
import sys
import time
import os

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = f"{ROOT}/data/urls_custom/mediapool-bg.tsv"
WIN_LO, WIN_HI = "2026-09-25", "2026-10-25"
BASE = "https://www.mediapool.bg"


def fetch_retry(url, tries=5, pause=10):
    for i in range(tries):
        status, body, _ = fetch(url)
        if status == 200 and body:
            return status, body
        time.sleep(pause)
    return status, body or ""


def route_rest():
    """Posts from the site's own WP REST API, paginated. Returns {url: date}."""
    # Buffer a full day on each side so any local-vs-GMT interpretation of
    # after/before still covers the window; strict filtering happens below.
    api = (f"{BASE}/wp-json/wp/v2/posts"
           f"?after=2026-09-24T00:00:00&before=2026-10-26T23:59:59"
           f"&per_page=100&_fields=date,link")
    found = {}
    page = 1
    while True:
        status, body = fetch_retry(f"{api}&page={page}")
        if status != 200:
            raise RuntimeError(f"REST API page {page}: HTTP {status}")
        posts = json.loads(body)
        if not isinstance(posts, list):
            raise RuntimeError(f"REST API page {page}: not a list")
        for p in posts:
            d = (p.get("date") or "")[:10]
            u = (p.get("link") or "").strip()
            if u and WIN_LO <= d <= WIN_HI:
                found.setdefault(u, d)
        if len(posts) < 100:
            break
        page += 1
        if page > 50:
            break
    return found


def route_sitemaps():
    """post-sitemap lastmod + news-sitemap publication_date. Returns {url: date}."""
    found = {}
    for i in (1, 2, 3):
        status, body = fetch_retry(f"{BASE}/post-sitemap{i}.xml")
        if status != 200:
            continue
        for block in re.findall(r"<url>(.*?)</url>", body, re.S):
            loc = re.search(r"<loc>(.*?)</loc>", block)
            lm = re.search(r"<lastmod>(.*?)</lastmod>", block)
            if not loc:
                continue
            d = (lm.group(1)[:10] if lm else "")
            if WIN_LO <= d <= WIN_HI:
                found.setdefault(loc.group(1).strip(), d)
    # News sitemap (only recent ~3 days) carries true publication dates.
    status, body = fetch_retry(f"{BASE}/news-sitemap.xml")
    if status == 200:
        for block in re.findall(r"<url>(.*?)</url>", body, re.S):
            loc = re.search(r"<loc>(.*?)</loc>", block)
            pd = re.search(r"publication_date[^>]*>(.*?)</", block)
            if not loc:
                continue
            d = (pd.group(1)[:10] if pd else "")
            if WIN_LO <= d <= WIN_HI:
                found[loc.group(1).strip()] = d  # publication_date wins
    return found


def main():
    source, found = None, {}
    try:
        found = route_rest()
        source = "rest-api"
    except Exception as e:
        print(f"REST route failed ({e}); falling back to sitemaps", file=sys.stderr)
    if not found:
        found = route_sitemaps()
        source = "sitemaps"
    if not found:
        print("ERROR: no URLs from any route", file=sys.stderr)
        return 1

    rows = sorted((u, d) for u, d in found.items())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")

    per = {}
    for u, d in rows:
        per[d] = per.get(d, 0) + 1
    print(f"route={source} wrote {len(rows)} URLs to {OUT}")
    for d in sorted(per):
        print(f"{d}\t{per[d]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
