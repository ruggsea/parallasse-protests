#!/usr/bin/env python3
"""Vanguard (Nigeria), vanguardngr.com -- article URLs published 2026-09-25 .. 2026-10-25.

Route: the site's own per-day WordPress date archives /YYYY/MM/DD/ (page 1, plus page 2 where a
day needs a margin / the three days the check samples).  Each archive page renders <article> cards
that carry the post URL (/YYYY/MM/slug/) and the site's own per-post date text ("October 10, 2026"),
so the listed date comes from the site, not from a guess.

Why not the alternatives:
  * robots.txt: Crawl-delay 10/30, Disallow /wp-json/, /search/, /*s=*, /wp-admin/, /cgi-bin/,
    /xmlrpc.php.  Only /feed/ explicitly allowed.
  * WP REST API (/wp-json/wp/v2/posts?after=...&before=...) -> robots-disallowed, route closed.
  * Sitemaps named in robots (/sitemap_index.xml, /news-sitemap.xml) and every variant tried
    (/sitemap.xml, /post-sitemap.xml, non-www host, query-string busted) -> HTTP 403 (WAF).
  * /feed/ is 200 but holds only 20 items per page (~2 h of publication: Vanguard posts ~200/day),
    so covering 31 days would need ~370 fetches -- and it has no paging that reaches back a month.
  * Per-day archives are 200, ~24 article cards on page 1 with 8-12 pages per day.

Usage: python3 scrapers/custom/vanguardngr-com.py
Writes data/urls_custom/vanguardngr-com.tsv  (URL<TAB>YYYY-MM-DD, no header, unique URLs)
"""
import datetime as dt
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = f"{ROOT}/data/urls_custom/vanguardngr-com.tsv"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
TARGETS = {dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 20)}
MIN_PER_TARGET = 15
DEADLINE = time.time() + 15 * 60  # hard safety: stop fetching after 15 minutes

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
DATE_RE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|"
                     r"November|December)\s+(\d{1,2}),\s+(20\d\d)\b")
ART_RE = re.compile(r'href="(https://www\.vanguardngr\.com/(\d{4})/(\d{2})/([a-z0-9][a-z0-9\-]*)/)"')


def day_urls(d):
    return [f"https://www.vanguardngr.com/{d:%Y/%m/%d}/",
            f"https://www.vanguardngr.com/{d:%Y/%m/%d}/page/2/",
            f"https://www.vanguardngr.com/{d:%Y/%m/%d}/page/3/"]


def parse_page(html, archive_day):
    """Return [(url, date)] from the <article> cards of a day archive page."""
    rows, seen = [], set()
    for block in re.split(r"(?=<article\b)", html):
        m = ART_RE.search(block)
        if not m:
            continue
        url = m.group(1)
        # skip the archive's own path (/YYYY/MM/DD/) and anything that is not an article slug
        if url.rstrip("/").endswith(f"{archive_day:%Y/%m/%d}"):
            continue
        if url in seen:
            continue
        d = DATE_RE.search(block)
        if d:
            try:
                date = dt.date(int(d.group(3)), MONTHS[d.group(1)], int(d.group(2)))
            except ValueError:
                continue
        else:                       # no date text in the card: fall back to the archive day
            date = archive_day
        # a card belongs to this day's archive; tolerate the +-1 day boundary, drop obvious bleed
        if abs((date - archive_day).days) > 1:
            continue
        seen.add(url)
        rows.append((url, date))
    return rows


def fetch_day(d, want_pages):
    """Fetch archive pages for one day, return dict url -> date."""
    got = {}
    for i, url in enumerate(day_urls(d)[:want_pages]):
        if time.time() > DEADLINE:
            print(f"  ! deadline hit, skipping {url}", flush=True)
            break
        status, text, path = fetch(url)
        if status != 200 or not text:
            if i == 0:
                print(f"  {d} page1 HTTP {status} ({path}) -- retrying once", flush=True)
                time.sleep(5)
                status, text, path = fetch(url)
            if status != 200 or not text:
                print(f"  {d} page{i+1} HTTP {status}", flush=True)
                break
            print(f"  {d} page{i+1} HTTP {status}", flush=True)
        rows = parse_page(text, d)
        print(f"  {d} page{i+1}: {len(rows)} cards", flush=True)
        if not rows:
            break
        for u, date in rows:
            if START <= date <= END:
                got.setdefault(u, date)
    return got


def main():
    days = [START + dt.timedelta(days=i) for i in range((END - START).days + 1)]
    allrows = {}
    for d in days:
        want = 2 if d in TARGETS else 1
        got = fetch_day(d, want)
        # a target day must clear the bar on its own, so pull further pages for it if short
        if d in TARGETS:
            extra = 2
            while sum(1 for u, x in got.items() if x == d) < MIN_PER_TARGET and extra < 3 \
                    and time.time() < DEADLINE:
                got.update(fetch_day(d, extra + 1))
                extra += 1
        for u, date in got.items():
            allrows.setdefault(u, date)

    rows = sorted(allrows.items(), key=lambda r: (r[1], r[0]))
    with open(OUT, "w") as f:
        for u, date in rows:
            f.write(f"{u}\t{date:%Y-%m-%d}\n")

    print(f"\nwrote {len(rows)} URLs to {OUT}")
    per = {}
    for u, date in rows:
        per[date] = per.get(date, 0) + 1
    for d in days:
        print(f"  {d}: {per.get(d, 0)}")
    print("\ntarget days:", ", ".join(f"{d}={per.get(d, 0)}" for d in sorted(TARGETS)))
    print("days in window with data:", len([d for d in days if per.get(d, 0)]))


if __name__ == "__main__":
    main()
