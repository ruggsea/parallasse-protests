#!/usr/bin/env python3
"""Scrape The Wire (thewire.in) article URLs for 2026-09-25 .. 2026-10-25 (site local +05:30).

Route (verified 2026-10-26):
- thewire.in is a Cloudflare-fronted React SPA: every path on thewire.in/www returns the same
  11.5 KB JS shell, so /feed/, /sitemap.xml and /wp-json on the main domain are unusable.
- m.thewire.in is server-rendered: /sitemap.xml is a real sitemap index, and article pages
  (https://m.thewire.in/article/<section>/<slug>) contain full text + JSON-LD datePublished.
- The WordPress backend is cms.thewire.in: /wp-json/wp/v2/posts is a live REST API whose
  'date' field (site local time, +05:30) matches the mobile page's JSON-LD datePublished to
  the second (verified: both 2026-10-26T14:29:05 for the Karnataka electoral-roll article).
- robots.txt (both domains) is permissive: only Disallow: /*?fromNewsdog* on the main domain.
So: paginate the REST API newest-first until before the window start, map each canonical
thewire.in link to its m.thewire.in/article/ mirror, list date = date-part of REST 'date'.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/thewire-in.tsv"
API = "https://cms.thewire.in/wp-json/wp/v2/posts"
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"


def to_mobile(url: str):
    """Map a canonical thewire.in article link to its m.thewire.in/article/ mirror."""
    m = re.match(r"https://(www\.)?thewire\.in(/.+)$", url)
    if not m:
        return None
    path = m.group(2).lstrip("/")
    # already article-like or section/slug; mobile routes articles under /article/
    if path.startswith("article/"):
        return f"https://m.thewire.in/{path}"
    return f"https://m.thewire.in/article/{path}"


def main():
    posts = {}  # mobile_url -> date (YYYY-MM-DD)
    page = 1
    total = 0
    while True:
        url = f"{API}?per_page=100&_fields=date,link&page={page}"
        status, text, _ = fetch(url)
        if status != 200:
            print(f"page {page}: status {status}, stopping", flush=True)
            break
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            print(f"page {page}: unparseable body, stopping", flush=True)
            break
        if not isinstance(data, list) or not data:
            break
        oldest = "9999"
        for item in data:
            date = (item.get("date") or "")[:10]
            mobile = to_mobile(item.get("link") or "")
            oldest = min(oldest, date)
            total += 1
            if mobile and WIN_START <= date <= WIN_END:
                posts[mobile] = date
        print(f"page {page}: {len(data)} posts, oldest {oldest}, in-window so far {len(posts)}", flush=True)
        if oldest < WIN_START:
            break
        if len(data) < 100:
            break
        page += 1
        if page > 60:
            print("safety: page cap hit", flush=True)
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    per_day = {}
    lines = []
    for u, d in sorted(posts.items(), key=lambda kv: (kv[1], kv[0])):
        lines.append(f"{u}\t{d}")
        per_day[d] = per_day.get(d, 0) + 1
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")


if __name__ == "__main__":
    main()
