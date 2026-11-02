#!/usr/bin/env python3
"""Face TV (face.ba, Bosnia and Herzegovina) - article URLs for 2026-09-25..2026-10-25.

Route: the site is WordPress 7.x with Hummingbird caching. robots.txt is HTTP 404
(no rules -> fetch treated as assumed_open), /sitemap.xml, /wp-sitemap.xml,
/sitemap_index.xml, /news-sitemap.xml and /sitemap-news.xml are all HTTP 404, so there is
no sitemap route at all. /feed/ works but only serves ~10 items per page (and 2026-10-25
came back short), so it is a lossy route. The open WP REST API is complete and carries the
site's own publication date:

    /wp-json/wp/v2/posts?per_page=100&page=N
        &after=2026-09-25T00:00:00&before=2026-10-26T00:00:00
        &orderby=date&order=desc&_fields=id,date,link

"date" is the site-local publication timestamp (Europe/Sarajevo), which is the date the
site states for the article; "link" is the canonical article URL. Pagination stops when a
page returns fewer than per_page=100 items, an empty list, or an HTTP 400 (page out of
range), which is what WP answers past the last page.

Writes data/urls_custom/face-ba.tsv, one line "URL<TAB>YYYY-MM-DD", no header, unique URLs.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if not (ROOT / "data").is_dir():                      # fallback: <repo>/scrapers/custom/this.py
    ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "face-ba.tsv"

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 26)          # exclusive upper bound


def api_url(page):
    return (
        "https://face.ba/wp-json/wp/v2/posts"
        f"?per_page=100&page={page}"
        "&after=2026-09-25T00:00:00&before=2026-10-26T00:00:00"
        "&orderby=date&order=desc&_fields=id,date,link"
    )


def collect():
    """Return dict date(YYYY-MM-DD) -> list of URLs, from the paginated WP REST API."""
    by_date = defaultdict(list)
    seen = set()
    page = 1
    while page <= 60:
        url = api_url(page)
        status, text, _ = fetch(url)
        if status != 200:
            print(f"  page {page}: HTTP {status} -> stop", file=sys.stderr)
            break
        try:
            posts = json.loads(text)
        except ValueError:
            print(f"  page {page}: not JSON -> stop", file=sys.stderr)
            break
        if not isinstance(posts, list) or not posts:
            print(f"  page {page}: empty -> stop", file=sys.stderr)
            break
        new = 0
        for post in posts:
            link = (post.get("link") or "").strip()
            raw_date = (post.get("date") or "").strip()
            if not link or len(raw_date) < 10:
                continue
            try:
                dt = datetime.fromisoformat(raw_date[:10])
            except ValueError:
                continue
            if not (START <= dt < END):
                continue
            day = dt.strftime("%Y-%m-%d")
            if link in seen:
                continue
            seen.add(link)
            by_date[day].append(link)
            new += 1
        print(f"  page {page}: {len(posts)} posts, {new} kept", file=sys.stderr)
        if len(posts) < 100:
            break
        page += 1
    return by_date


def main():
    by_date = collect()
    days = sorted(by_date)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with OUT.open("w", encoding="utf-8") as fh:
        d0 = datetime(2026, 9, 25)
        for i in range(31):
            day = (d0 + timedelta(days=i)).strftime("%Y-%m-%d")
            urls = sorted(set(by_date.get(day, [])))
            for u in urls:
                fh.write(f"{u}\t{day}\n")
            total += len(urls)
            print(f"{day}: {len(urls)} URLs")
    print(f"total {total} URLs, {len(days)} days, written to {OUT}")


if __name__ == "__main__":
    main()
