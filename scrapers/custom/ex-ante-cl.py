#!/usr/bin/env python3
"""ex-ante.cl (Ex-Ante, Chile) - article URLs 2026-09-25..2026-10-25.

Route: permissive robots.txt -> WordPress REST API /wp-json/wp/v2/posts with
per-day after/before in site-local time. The site runs in America/Santiago
(UTC-3 during the window); the REST 'date' field is the local post date and
equals the page JSON-LD datePublished / <time class="fecha"> date exactly
(verified on samples, e.g. 2026-10-10T19:58:26 == 2026-10-10T19:58:26-03:00).

The Rank Math post-sitemaps (post-sitemap1..80) are stale (newest lastmod
2026-09-02) and the news-sitemap holds only ~48h, so neither covers the
window. The per-day REST count is the site's own stated publication count.

Output: data/urls_custom/ex-ante-cl.tsv  (URL<TAB>YYYY-MM-DD, unique, no header)
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/ex-ante-cl.tsv"
API = "https://www.ex-ante.cl/wp-json/wp/v2/posts"
START = date(2026, 9, 25)
END = date(2026, 10, 25)


def day_urls(day: date):
    """All posts published on `day` in site-local time, paginated."""
    after = day.isoformat() + "T00:00:00"
    before = (day + timedelta(days=1)).isoformat() + "T00:00:00"
    out = []
    page = 1
    while True:
        url = (f"{API}?per_page=100&_fields=link,date"
               f"&after={after}&before={before}&page={page}")
        status, body, _ = fetch(url)
        if status != 200 or not body:
            print(f"  ! {url} -> status {status}", file=sys.stderr)
            break
        try:
            items = json.loads(body)
        except ValueError:
            print(f"  ! {url} -> unparseable body", file=sys.stderr)
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            link = it.get("link", "").strip()
            d = (it.get("date") or "")[:10]
            if link.startswith("http") and d:
                out.append((link, d))
        if len(items) < 100:
            break
        page += 1
        if page > 10:  # hard cap: site publishes <20 posts/day
            break
    return out


def main():
    found = {}  # url -> date
    counts = {}
    d = START
    while d <= END:
        for link, pd in day_urls(d):
            if pd == d.isoformat():  # keep only what the API dated this day
                if link not in found:
                    found[link] = pd
        counts[d.isoformat()] = sum(1 for v in found.values() if v == d.isoformat())
        d += timedelta(days=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for link, pd in lines:
            f.write(f"{link}\t{pd}\n")

    total = len(found)
    print(f"wrote {total} unique URLs to {OUT}")
    for day, n in sorted(counts.items()):
        print(f"{day}: {n}")
    low = [k for k in ("2026-09-30", "2026-10-10", "2026-10-20") if counts.get(k, 0) < 15]
    if low:
        print("low-volume days (<15): " + ", ".join(f"{k}={counts.get(k,0)}" for k in low))


if __name__ == "__main__":
    main()
