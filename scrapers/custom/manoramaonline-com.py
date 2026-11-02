#!/usr/bin/env python3
"""manoramaonline.com (Malayala Manorama, India) article-URL scraper, 2026-09-25 .. 2026-10-25.

Route: the site-wide chronological firehose listing
    https://www.manoramaonline.com/news/latest-news.html?page=N
page 1 = today, each further page walks back roughly one day (page 30 = 2026-09-30,
page 40 = 2026-09-22, page 60 = 2026-09-05, measured 2026-10-25).  Each page is a
server-rendered AEM listing carrying ~250 article links to every section of the paper
(news, district-news, business, sports, global-malayali, premium, ...).

Article URLs are day-permalinks of the form
    /<section>/<subsection>/YYYY/MM/DD/<slug>.html
and the day in the path is the outlet's own publication date: verified against
"article:published_time" on sampled articles from 2026-10-25, where they are identical
to the minute (e.g. /news/latest-news/2026/10/25/cheranalloor-car-crash... ->
2026-10-25T22:56:22+05:30).  So the date written to the TSV comes from the site.

Dead ends checked (all via polite_fetch):
  /robots.txt                     200, no Sitemap: line; /rss/ and /content/mm/mo/* disallowed
  /sitemap.xml                    200 but it is an AEM page dump, not a sitemap index
  /sitemap/google-news-<section>.xml  200 and every one of the 62 is an EMPTY <urlset>
  /news-sitemap.xml, /sitemap-index.xml   404
  /news/latest-news.html          200 (section landing, but paged firehose is the useful part)
  /news/latest-news/2026/10/20.html       404 (no per-day archive page)
  /archive/2026/10/20.html        404

Output: URL<TAB>YYYY-MM-DD, unique, sorted by date then URL, no header.
All HTTP goes through scrapers/polite_fetch.fetch (robots.txt first, per-host rate limit,
every request logged).
"""
import re
import sys
import time
import datetime as dt
import collections
from pathlib import Path

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.manoramaonline.com"
LISTING = BASE + "/news/latest-news.html?page=%d"
OUT = ROOT / "data/urls_custom/manoramaonline-com.tsv"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
DEADLINE = time.time() + 15 * 60
MAX_PAGE = 42                      # window ends ~page 37; margin for safety
EMPTY_PAGE_STOP = 2                # stop after this many pages with nothing in the window

ART_RE = re.compile(r'href="(?:' + re.escape(BASE) + r')?(/[^"\s]*?/(\d{4})/(\d{2})/(\d{2})/[^"\s]+?\.html)(?:[?"#][^"]*)?"')
# sections whose pages are link farms / galleries rather than articles with body text
JUNK_SECTIONS = ("web-stories", "kerala-lottery-results", "lottery-results")


def get(url, tries=3):
    for n in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:
            print("  ! %s -> %r" % (url, exc), flush=True)
            status, text = 0, None
        if status == 200 and text:
            return text
        if status == -1:                        # robots disallow: never retried, never bypassed
            print("  ! robots-disallowed %s" % url, flush=True)
            return None
        time.sleep(1.0 * (n + 1))
    return None


def is_junk(path):
    low = path.lower()
    return any(("/" + s + "/") in low or low.startswith("/" + s + "/") for s in JUNK_SECTIONS)


def main():
    found = {}          # path -> date string
    empty_pages = 0
    pages_done = 0
    for page in range(1, MAX_PAGE + 1):
        if time.time() > DEADLINE:
            print("  deadline reached, stopping at page %d" % page, flush=True)
            break
        body = get(LISTING % page)
        pages_done += 1
        if not body:
            print("  page %d: no body, skipping" % page, flush=True)
            continue
        in_window = 0
        page_dates = collections.Counter()
        for m in ART_RE.finditer(body):
            path = m.group(1)
            try:
                d = dt.date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
            except ValueError:
                continue
            page_dates[d] += 1
            if not (START <= d <= END):
                continue
            if is_junk(path):
                continue
            in_window += 1
            found.setdefault(path, d.isoformat())
        span = ("%s..%s" % (min(page_dates), max(page_dates))) if page_dates else "-"
        print("  page %2d: %d links, %d in window, dates %s" % (page, sum(page_dates.values()), in_window, span), flush=True)
        if in_window:
            empty_pages = 0
        else:
            empty_pages += 1
            if empty_pages >= EMPTY_PAGE_STOP:
                break
        # Every page also repeats a handful of pinned links dated today, so judge
        # progress by the page's own (non-newest) day: once that has walked past
        # the window start, all older pages are outside it.
        if len(page_dates) > 1:
            own = sorted(page_dates)[-2]
            if own < START:
                print("  walked past the window start (%s), done after %d pages" % (START, page), flush=True)
                break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    tmp = OUT.with_suffix(".tsv.tmp")
    with open(tmp, "w") as f:
        for path, d in rows:
            f.write("%s%s\t%s\n" % (BASE, path, d))
    tmp.replace(OUT)

    per_day = collections.Counter(d for _, d in rows)
    print("\nwrote %d unique URLs to %s after %d listing pages" % (len(rows), OUT, pages_done), flush=True)
    day = START
    while day <= END:
        print("  %s\t%d" % (day.isoformat(), per_day.get(day.isoformat(), 0)), flush=True)
        day += dt.timedelta(days=1)
    missing = [day.isoformat() for day in
               (START + dt.timedelta(days=i) for i in range((END - START).days + 1))
               if per_day.get(day.isoformat(), 0) < 15]
    if missing:
        print("  days with fewer than 15 URLs: %s" % ", ".join(missing), flush=True)


if __name__ == "__main__":
    main()
