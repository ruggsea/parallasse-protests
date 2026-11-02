#!/usr/bin/env python3
"""ambito.com (Ambito Financiero, Argentina) - article URLs 2026-09-25..2026-10-25.

Route that works:
  robots.txt (200, permissive) advertises /sitemap.xml, /sitemap-news.xml and
  /sitemap/news-full/sitemap-index.xml. The flat /sitemap.xml holds only the ~68 newest
  articles and /sitemap-news.xml only the last ~2-3 days, so neither covers a month.
  /sitemap/news-full/sitemap-index.xml lists one gzip sitemap per MONTH back to 1998
  (/sitemap/news-full/sitemap-YYYYMM.xml.gz), each a flat urlset with <lastmod> per
  article. Two files (202609, 202610) cover the window in 2 requests -> ~4000 URLs.

Date caveat and its fix: <lastmod> is the CMS edit time, so an updated article carries a
date later than its publication (measured: 1 of 67 random articles off by 2+ days).
Every article page carries JSON-LD datePublished. Article ids in the URLs (-n6337685) are
monotone in time, so the id gives an independent estimate of the publication day: an item
whose lastmod sits more than a day above the median lastmod of its id neighbourhood is a
rewrite/scheduled piece, and only those (~350 of 4000) are fetched and re-dated from their
own datePublished. The rest keep lastmod, which the neighbourhood test bounds to +/-1 day.

Output: data/urls_custom/ambito-com.tsv - "URL<TAB>YYYY-MM-DD", unique URLs, no header.
Standalone: run with the repo venv, e.g. .venv/bin/python3 scrapers/custom/ambito-com.py
"""
import collections
import os
import re
import statistics
import sys
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/ambito-com.tsv")
BASE = "https://www.ambito.com"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MAX_VERIFY = 700          # page fetches allowed for drift correction (polite rate ~2/s)
NEIGHBOURS = 50           # id neighbourhood size for the lastmod trend

ENTRY = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>", re.S)
NEWS_ENTRY = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>.*?<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>", re.S)
PUB_JSONLD = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
PUB_META = re.compile(r'property="article:published_time"\s+content="([^"]+)"')
ARTICLE_ID = re.compile(r"-n(\d+)")


def get(url):
    status, text, _path = fetch(url)
    print(f"# {status} {url}", file=sys.stderr)
    return text if status == 200 else None


def months():
    out, y, m = [], START.year, START.month
    while (y, m) <= (END.year, END.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def day_of(stamp):
    """First 10 chars of an ISO timestamp; local-date keeping the site's own offset."""
    return stamp[:10]


def in_window(day):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    return START <= d <= END


def article_id(url):
    m = ARTICLE_ID.search(url)
    return int(m.group(1)) if m else None


def page_date(url):
    """Publication day from the article page itself (JSON-LD, then meta tag)."""
    text = get(url)
    if not text:
        return None
    for rx in (PUB_JSONLD, PUB_META):
        m = rx.search(text)
        if m:
            return day_of(m.group(1))
    return None


def main():
    # 1. monthly sitemaps -> url: earliest lastmod seen
    last = {}
    for m in months():
        text = get(f"{BASE}/sitemap/news-full/sitemap-{m}.xml.gz")
        if not text:
            continue
        for url, lm in ENTRY.findall(text):
            if not url.startswith("http") or not in_window(day_of(lm)):
                continue
            if url not in last or lm < last[url]:
                last[url] = lm

    # 2. exact publication timestamps for the freshest couple of days
    text = get(f"{BASE}/sitemap-news.xml")
    if text:
        for url, pub in NEWS_ENTRY.findall(text):
            if in_window(day_of(pub)):
                last[url] = pub

    print(f"# sitemap entries in window: {len(last)}", file=sys.stderr)

    # 3. flag items whose lastmod sits above the lastmod trend of their id neighbourhood
    dated = {u: day_of(s) for u, s in last.items()}
    ids = {u: article_id(u) for u in dated}
    ordered = sorted((u for u in dated if ids[u] is not None), key=lambda u: ids[u])
    ordinal = [date.fromisoformat(dated[u]).toordinal() for u in ordered]
    flagged = [u for u in dated if ids[u] is None]
    for k, url in enumerate(ordered):
        lo, hi = max(0, k - NEIGHBOURS), min(len(ordered), k + NEIGHBOURS + 1)
        if ordinal[k] - statistics.median(ordinal[lo:hi]) > 1.0:
            flagged.append(url)
    print(f"# drift check: {len(flagged)} of {len(dated)} items re-dated from their page",
          file=sys.stderr)

    # 4. re-date the flagged ones from the page itself
    fixed = 0
    for url in sorted(flagged)[:MAX_VERIFY]:
        d = page_date(url)
        if d and in_window(d):
            if dated[url] != d:
                fixed += 1
            dated[url] = d
    print(f"# page dates used: {fixed} items moved, {len(flagged) - fixed} confirmed",
          file=sys.stderr)

    # 5. write, unique URLs, sorted by date
    by_day = collections.defaultdict(list)
    for url, d in dated.items():
        by_day[d].append(url)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n = 0
    with open(OUT, "w") as f:
        for d in sorted(by_day):
            for url in sorted(set(by_day[d])):
                f.write(f"{url}\t{d}\n")
                n += 1
    for d in sorted(by_day):
        print(f"{d}\t{len(set(by_day[d]))}")
    print(f"# wrote {n} URLs to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
