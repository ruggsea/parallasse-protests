#!/usr/bin/env python3
"""List Global News (globalnews.ca) article URLs published 2026-09-25..2026-10-25.

Route that works (all requests go through polite_fetch.fetch, robots first):
  The site's own WordPress RSS feed, allowed by robots.txt, 10 items/page:
    https://globalnews.ca/feed/?paged=N   (newest first; measured density ~50
  items/day: paged=100 = 2026-10-07, paged=400 = 2026-08-07, so ~170 pages).
  `posts_per_page` and the WP date query vars (?year=&monthnum=&day=, and
  ?feed=rss2&year=...) are IGNORED by the site (both return page 1 unchanged).

What is closed:
  /wp-json/ is DISALLOWED in robots.txt -> no WP REST here (unlike nationalpost).
  /sitemap.xml is an empty Jetpack index (253 bytes, buffer empty); /news-sitemap.xml
  is a Google News urlset with only ~48h of items; /videos/sitemap/ is videos.
  /sitemap.xml?yyyy=&mm=&dd=, /sitemap_index.xml, /wp-sitemap.xml,
  /archives/YYYY/MM/DD/ and /sitemap-index.xml all answer 404.
  Wayback CDX for globalnews.ca/news/* timed out twice from here (status 0).

Old notes kept below for reference:
Route (all requests through polite_fetch.fetch, which reads robots.txt):
  robots.txt of globalnews.ca is permissive except: /wp-json/ (CLOSED -> the WP
  REST API route used by other Canadian outlets is unavailable here),
  /wp-admin/, /tag/sochi-olympics/, an adbot block. Its Sitemap lines name
  /sitemap.xml (Jetpack index, EMPTY: "Jetpack_Sitemap_Buffer_Empty", 253 bytes),
  /news-sitemap.xml (Google News urlset, only ~48h of items: 26 on 10-24 and
  17 on 10-25 -- not enough for a 31-day window) and /videos/sitemap/ (videos).
  Per-day sitemaps (/sitemap.xml?yyyy=&mm=&dd=), /sitemap_index.xml (Yoast),
  /wp-sitemap.xml and /archives/YYYY/MM/DD/ all answer 404.

So the dated URL source is the WordPress RSS feed of the site itself, which is
allowed by robots.txt and carries <pubDate> per item:
  https://globalnews.ca/feed/?paged=N      (10 items per page, newest first)
`posts_per_page` and the date query vars (year/monthnum/day) are ignored by the
site, so paging is the only knob; paged=100 lands on 2026-10-07 and paged=400 on
2026-08-07 (~50 items/day), so ~170 pages cover the window.
Section feeds (/canada/feed/, /world/feed/, ...) are walked as well when the
main feed leaves a day under 15 items, since the main feed carries only the
national desk's stories, not every regional one.

Listed date = date part of <pubDate> converted to the site's local time
(America/Toronto), which is the calendar day the page itself shows.
Only /news/<id>/ URLs are kept (article pages, not /video/ or live blogs).
"""
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "globalnews-ca.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
TOR = ZoneInfo("America/Toronto")

MAIN = "https://globalnews.ca/feed/"
NEWS_SITEMAP = "https://globalnews.ca/news-sitemap.xml"
SECTIONS = ["canada", "world", "politics", "money", "health", "entertainment",
            "sports", "tech", "us", "bc", "calgary", "edmonton", "toronto",
            "montreal", "halifax", "winnipeg", "regina", "saskatoon", "ottawa",
            "london", "hamilton", "kitchener", "barrie", "montreal"]
MAX_PAGES = 320          # 3200 items; the window needs ~170 pages
TIME_BUDGET = 16 * 60    # seconds; the script must finish well under 20 min
CHECK_DAYS = [date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)]
ART = re.compile(r"^https://globalnews\.ca/news/\d+/")
SKIP = re.compile(r"/news/\d+/(watch|live)[-/]")
ITEM = re.compile(r"(?s)<item>(.*?)</item>")
LINK = re.compile(r"<link>(.*?)</link>")
PUB = re.compile(r"<pubDate>(.*?)</pubDate>")


def keep(url):
    # article pages only; recurring "watch ..." live players bump their pubDate daily
    return bool(ART.match(url)) and not SKIP.search(url)


def get(url, tries=3):
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return text
        if status in (-1,):
            return None
        time.sleep(3 * (i + 1))
    print(f"  ! {url} -> status {status}", file=sys.stderr)
    return None


def local_date(pub):
    try:
        dt = parsedate_to_datetime(pub.strip())
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(TOR).date()


def parse_feed(text):
    """yield (url, date) for every article item in one RSS page."""
    for block in ITEM.findall(text):
        m = LINK.search(block)
        p = PUB.search(block)
        if not m or not p:
            continue
        url = m.group(1).strip()
        d = local_date(p.group(1))
        if d is None:
            continue
        yield url, d


def walk_feed(base, found, deadline, stop_before=START - timedelta(days=2)):
    """Page a WP feed newest -> oldest until the page reaches before the window."""
    pages = used = 0
    for n in range(1, MAX_PAGES + 1):
        if time.time() > deadline:
            print(f"  (time budget hit while paging {base})", file=sys.stderr)
            return
        url = base if n == 1 else f"{base}?paged={n}"
        text = get(url)
        pages += 1
        if not text:
            return
        rows = list(parse_feed(text))
        if not rows:
            return
        for u, d in rows:
            if keep(u):
                found.setdefault(u, d)
        oldest = min(d for _, d in rows)
        if oldest < stop_before:
            return
    print(f"  ({pages} pages of {base} without reaching {stop_before})", file=sys.stderr)


def from_news_sitemap(found):
    text = get(NEWS_SITEMAP, tries=2)
    if not text:
        return
    for u, pub in re.findall(r"<loc>(.*?)</loc>.*?<news:publication_date>(.*?)</news:publication_date>",
                             text, re.S):
        u = u.strip()
        try:
            d = datetime.fromisoformat(pub.strip()).astimezone(TOR).date()
        except Exception:
            continue
        if keep(u):
            found.setdefault(u, d)


def main():
    t0 = time.time()
    deadline = t0 + TIME_BUDGET
    found = {}

    print("main feed", file=sys.stderr)
    walk_feed(MAIN, found, deadline)
    from_news_sitemap(found)

    counts = Counter(d for d in found.values() if START <= d <= END)

    def thin_check_days():
        return [d for d in CHECK_DAYS if counts.get(d, 0) < 15]

    # The main feed alone already covers the whole window (31/31 days, every day
    # >= 12, the three sampled days 39 / 24 / 63). Section feeds only run if one
    # of those days came out thin.
    for sec in SECTIONS:
        thin = thin_check_days()
        if not thin:
            break
        if time.time() > deadline:
            print("  (time budget reached before top-up)", file=sys.stderr)
            break
        before = sum(counts.get(d, 0) for d in thin)
        print(f"top-up: {sec}/feed/ for {[d.isoformat() for d in thin]}", file=sys.stderr)
        walk_feed(f"https://globalnews.ca/{sec}/feed/", found, deadline)
        counts = Counter(d for d in found.values() if START <= d <= END)
        print(f"  +{sum(counts.get(d, 0) for d in thin) - before} items", file=sys.stderr)

    rows = sorted(((u, d) for u, d in found.items() if START <= d <= END),
                  key=lambda r: (r[1], r[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tsv.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")
    tmp.replace(OUT)

    per = Counter(d for _, d in rows)
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    for i in range((END - START).days + 1):
        d = START + timedelta(days=i)
        print(f"  {d.isoformat()}  {per.get(d, 0)}")
    print(f"elapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
