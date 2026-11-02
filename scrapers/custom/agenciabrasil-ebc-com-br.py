#!/usr/bin/env python3
"""Agência Brasil (agenciabrasil.ebc.com.br) article-URL scraper, 2026-09-25 .. 2026-10-25.

Route that works: the site's own "Últimas" listing, https://agenciabrasil.ebc.com.br/ultimas,
paginated with ?page=N (Drupal pager, 0-based).  Each card carries the outlet's own
publication stamp in the markup:

    <a href="/politica/noticia/2026-10/<slug>" class="titulo-noticia">...</a>
    <div class="data-publicacao"><span class="data">dom, 25/10/2026 - 11:10</span></div>

so the date written to the TSV is the site's stated publication date (America/Sao_Paulo),
not a crawl date.  Roughly 14 cards per page, ~3.5 pages per day of news.

Why not the sitemaps: robots.txt lists none, and /sitemap.xml is a Drupal xmlsitemap index
of 16 pages whose newest lastmod is 2020-02-11 (the sitemap has been stale since 2020, HTTP
200 but useless for 2026).  /news-sitemap.xml, /sitemap-news.xml, /sitemap_news.xml,
/google-news-sitemap.xml, /sitemap_index.xml all answer 404.  /rss.xml is stale too (items
from 2020-06).  /jsonapi is 404 (Drupal 7, no JSON:API).

Output: data/urls_custom/agenciabrasil-ebc-com-br.tsv, one line "URL<TAB>YYYY-MM-DD",
unique URLs, sorted by date then URL, no header.  Prints per-day counts.

Every HTTP request goes through scrapers/polite_fetch.fetch (robots.txt first, per-host
rate limit, every request logged, body cached).  robots.txt of agenciabrasil.ebc.com.br
(HTTP 200) disallows only /includes/, /misc/, /modules/, /profiles/, /scripts/, /themes/,
/admin/, /comment/reply/, /filter/tips/, /node/add/, /search/ and user-account paths;
/ultimas and the article paths are allowed.
"""
import sys
import re
import time
import datetime as dt
from collections import Counter
from pathlib import Path

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://agenciabrasil.ebc.com.br"
OUT = ROOT / "data/urls_custom/agenciabrasil-ebc-com-br.tsv"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)

DEADLINE = time.time() + 15 * 60          # hard stop well inside the 20 min budget
MAX_PAGES = 400                           # guard; the real stop is the date ordering

BLOCK_RE = re.compile(r'<div class="(?:ultima-noticia|noticia-destaque-interna)"')
LINK_RE = re.compile(r'href="(/[^"?#]+)"\s+class="titulo-noticia"')
LINK_RE2 = re.compile(r'href="(/[^"?#]+)"\s+class="titulo-noticia-interna"')
DATE_RE = re.compile(r'class="data">\s*(?:[A-Za-zÀ-ÿ]+,?\s*)?(\d{2})/(\d{2})/(\d{4})')
ART_PATH_RE = re.compile(r'^/[a-z0-9\-]+/(?:noticia|reportagem|entrevista|audio|video|foto)/\d{4}-\d{2}/')


def parse_listing(html):
    """Return [(url, date)] from one /ultimas page."""
    items = []
    blocks = BLOCK_RE.split(html)[1:]
    for b in blocks:
        m = LINK_RE.search(b) or LINK_RE2.search(b)
        if not m:
            continue
        d = DATE_RE.search(b[:4000])
        if not d:
            continue
        path = m.group(1)
        if not ART_PATH_RE.match(path):
            continue
        dd, mm, yy = int(d.group(1)), int(d.group(2)), int(d.group(3))
        try:
            date = dt.date(yy, mm, dd)
        except ValueError:
            continue
        items.append((BASE + path, date))
    return items


def main():
    found = {}          # url -> date
    pages = 0
    page = 0
    stop_slack = 0
    consecutive_empty = 0

    while page < MAX_PAGES and time.time() < DEADLINE:
        url = BASE + "/ultimas" + ("?page=%d" % page if page else "")
        status, text, _robots = fetch(url)
        pages += 1
        if status != 200 or not text:
            print("page %d -> HTTP %s, stopping" % (page, status), flush=True)
            consecutive_empty += 1
            if consecutive_empty >= 2:
                break
            page += 1
            continue
        consecutive_empty = 0
        items = parse_listing(text)
        new = 0
        for u, d in items:
            if START <= d <= END:
                if u not in found:
                    found[u] = d
                    new += 1
        if items:
            oldest = min(d for _, d in items)
            print("page %3d: %2d items, %2d new, oldest %s" % (page, len(items), new, oldest), flush=True)
            if oldest < START:
                stop_slack += 1
                # a few pages of slack: the listing is newest-first but a pinned item can
                # appear out of order; three pages older than the window ends the crawl.
                if stop_slack >= 3:
                    break
            else:
                stop_slack = 0
        else:
            print("page %3d: no items parsed (HTTP %s)" % (page, status), flush=True)
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
        page += 1

    if not found:
        print("NO URLS FOUND", flush=True)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    tmp = OUT.with_suffix(".tsv.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d.isoformat()))
    tmp.replace(OUT)

    per_day = Counter(d for _, d in rows)
    print("\nwrote %d unique URLs to %s (%d listing pages)" % (len(rows), OUT, pages), flush=True)
    day = START
    while day <= END:
        print("%s\t%d" % (day.isoformat(), per_day.get(day, 0)))
        day += dt.timedelta(days=1)
    missing = [d.isoformat() for d in (dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 20))
               if per_day.get(d, 0) < 15]
    print("check days under 15: %s" % (missing or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
