#!/usr/bin/env python3
"""rpp.pe (RPP Noticias, Peru) - list article URLs published 2026-09-25..2026-10-25.

Route (worked out by inspecting the site):
- robots.txt (200) allows /archivo/* (only old years 19*/200*/201*/2020* are disallowed)
  and all /sitemap/* sitemaps.
- /sitemap/news is a flat urlset with news:publication_date but only the ~200 newest
  URLs (2026-10-19..25) - not enough for the 31-day window.
- /sitemap/web/<section> sitemaps carry only <lastmod> (edit time, verified: an
  article published 10-24 carried lastmod 10-25) and only the ~200 newest per section.
- The daily archive /archivo/YYYY-MM-DD (dash form; the slash form 302s to the
  homepage) is the full per-day list: page 1 is static HTML with 30 articles, each
  carrying <time data-x="YYYY-MM-DDTHH:MM:SS-05:00">, and a "loadArticles" widget
  serves /archivo/YYYY-MM-DD/page-N as JSON {"succes":true,"nextPage":N+1|false,
  "html":...} with 10 more articles each, ending when nextPage is false.
- The date written per URL is the data-x timestamp date as the archive page states
  it (falls back to the archive day when absent).
"""
import json
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://rpp.pe"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/rpp-pe.tsv"

URL_RE = re.compile(
    r"https://rpp\.pe/[A-Za-z0-9\-]+(?:/[A-Za-z0-9\-]+){1,3}/[A-Za-z0-9\-]*(?:noticia|live|video-noticia|galeria)-\d+"
)
TS_RE = re.compile(r'data-x="(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}-05:00"')


def articles_from_html(html, fallback_day):
    """Yield (url, date) from one archive page body (HTML fragment)."""
    out = []
    for chunk in html.split("<article")[1:]:
        m = URL_RE.search(chunk)
        if not m:
            continue
        url = m.group(0)
        t = TS_RE.search(chunk)
        day = t.group(1) if t else fallback_day
        out.append((url, day))
    return out


def scrape_day(day):
    """Return list of (url, date) for one day's archive."""
    items = []
    s, body, _ = fetch(f"{BASE}/archivo/{day.isoformat()}")
    if s != 200 or not body:
        print(f"  ! page1 status {s}", file=sys.stderr)
        return items
    items += articles_from_html(body, day.isoformat())
    page = 2
    for _ in range(40):  # safety cap
        s, body, _ = fetch(f"{BASE}/archivo/{day.isoformat()}/page-{page}")
        if s != 200 or not body:
            print(f"  ! page{page} status {s}", file=sys.stderr)
            break
        try:
            d = json.loads(body)
        except ValueError:
            break
        if not d.get("succes"):
            break
        items += articles_from_html(d.get("html", ""), day.isoformat())
        nxt = d.get("nextPage")
        if not nxt or nxt <= page:
            break
        page = int(nxt)
    return items


def main():
    found = {}
    d = START
    while d <= END:
        iso = d.isoformat()
        items = scrape_day(d)
        n = 0
        for url, day in items:
            if day < iso:
                continue  # out of window (should not happen)
            if url in found:
                continue
            found[url] = day
            n += 1
        print(f"{iso}: {n} urls")
        d += timedelta(days=1)

    import os

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url, day in sorted(found.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{url}\t{day}\n")
    print(f"TOTAL: {len(found)} unique urls -> {OUT}")


if __name__ == "__main__":
    main()
