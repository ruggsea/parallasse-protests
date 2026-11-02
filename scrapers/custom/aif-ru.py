#!/usr/bin/env python3
"""Argumenty i Fakty (aif.ru) article URLs for 2026-09-25 .. 2026-10-25.

Route: robots.txt (https://aif.ru/robots.txt, HTTP 200) names one sitemap index,
https://aif.ru/sitemap.xml. That index lists 47 sitemaps; the ones with a recent
<lastmod> are the rolling news sitemaps sitemap_news_1.xml .. sitemap_news_21.xml.
There is no per-day or per-month sitemap and no date archive (/all/2026/09/30 and
/archive/2026-09-30 both 404), and article URLs carry no date.

Each news sitemap is a flat <urlset> of up to 40,000 article URLs (loc + lastmod +
changefreq + priority), and every URL inside them is an article path
(/politics/..., /society/..., /incidents/..., 2-3 path segments, no /gazeta/ pages).
Coverage of the window (measured 2026-10-27):
    sitemap_news_21.xml  2026-10-10 .. 2026-10-27   4,448 urls
    sitemap_news_20.xml  2026-05-01 .. 2026-10-23  40,000 urls
    sitemap_news_19.xml  2025-11-27 .. 2026-10-12  40,000 urls
so the three newest files together hold every article of the window. <lastmod> is the
publication timestamp on this site: for the 21 URLs re-fetched on 2026-09-30, 10-10 and
10-20 the page's own itemprop="datePublished" (and meta article:published_time) matched
the listed day exactly, 21/21; across an earlier random sample of 12 across the window,
11 matched exactly and one was one day off (an article rescheduled in the CMS).

Written date = date part of <lastmod>, taken from the newest sitemap file where the URL
appears. Output: data/urls_custom/aif-ru.tsv, "URL<TAB>YYYY-MM-DD", unique, no header.
"""

import re
import sys
import datetime
import collections
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "aif-ru.tsv"

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

INDEX_URL = "https://aif.ru/sitemap.xml"
# Fallback if the index cannot be fetched: the news-sitemap family, newest first.
FALLBACK_NEWS = ["https://aif.ru/sitemap_news_%d.xml" % n for n in range(21, 12, -1)]

URL_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
PAIR_RE = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>", re.S
)


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup: retry
            status, text = 0, str(exc)
        if status == 200 and text:
            return status, text
        if status in (429, 503, 0):
            continue
        return status, text
    return status, text


def news_sitemaps():
    """News sitemap locations from the index, newest first; fallback to the known family."""
    status, text = get(INDEX_URL)
    if status != 200 or "<sitemapindex" not in (text or ""):
        print("sitemap index unavailable (status %s), using known news sitemap family" % status)
        return FALLBACK_NEWS
    entries = PAIR_RE.findall(text)
    if not entries:
        entries = [(loc, "") for loc in URL_RE.findall(text)]
    news = []
    for loc, lastmod in entries:
        if not re.search(r"/sitemap_news(_\d+)?\.xml$", loc):
            continue
        num = int(re.search(r"_(\d+)\.xml$", loc).group(1)) if re.search(r"_(\d+)\.xml$", loc) else 999
        news.append((num, loc, lastmod[:10]))
    news.sort(reverse=True)  # newest file first (num desc; legacy sitemap_news.xml last-ish)
    # Only files the index itself says were touched on/after the window start can hold
    # articles of the window; that drops the dead 2021-2023 rolling files.
    fresh = [n for n in news if n[2] >= START.isoformat()]
    chosen = fresh if len(fresh) >= 2 else news[:5]
    print("index lists %d news sitemaps, %d touched since %s: %s" %
          (len(news), len(fresh), START.isoformat(),
           ", ".join(n[1].rsplit("/", 1)[-1] for n in chosen[:6])))
    return [loc for _, loc, _ in chosen]


def main():
    best = {}  # url -> (file_rank, lastmod_string); lower rank = newer file
    reaches_start = reaches_end = False
    in_window = 0
    for rank, loc in enumerate(news_sitemaps()):
        # Newest files first; the rolling news sitemaps overlap, so stop once one file
        # reaches forward past the window end and another back before its start (2 files).
        if rank >= 3 and reaches_start and reaches_end and in_window >= 300:
            print("window fully covered by %d news sitemaps, stopping" % rank)
            break
        status, text = get(loc)
        if status != 200 or not text:
            print("skip %s (status %s)" % (loc, status))
            continue
        pairs = PAIR_RE.findall(text)
        if not pairs:
            pairs = [(u, "") for u in URL_RE.findall(text)]
        new_in_window = 0
        oldest = "9999"
        for url, lastmod in pairs:
            day = lastmod[:10]
            if day and day < oldest:
                oldest = day
            if not day or not ("2026-09-25" <= day <= "2026-10-25"):
                continue
            if "/gazeta/" in url or url.rstrip("/").count("/") < 4:
                continue
            prev = best.get(url)
            if prev is None or rank < prev[0]:
                best[url] = (rank, lastmod)
                new_in_window += 1
        newest = max((lm[:10] for _u, lm in pairs if lm), default="")
        if oldest <= START.isoformat():
            reaches_start = True
        if newest >= END.isoformat():
            reaches_end = True
        in_window += new_in_window
        print("%s: %d urls, oldest lastmod %s, %d in window"
              % (loc.rsplit("/", 1)[-1], len(pairs), oldest, new_in_window))

    rows = []
    for url, (_rank, lastmod) in best.items():
        try:
            day = datetime.date.fromisoformat(lastmod[:10])
        except ValueError:
            continue
        if START <= day <= END:
            rows.append((url, day.isoformat()))
    rows.sort(key=lambda r: (r[1], r[0]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tsv.tmp")
    with open(tmp, "w") as fh:
        for url, day in rows:
            fh.write("%s\t%s\n" % (url, day))
    tmp.replace(OUT)

    per_day = collections.Counter(day for _url, day in rows)
    print("\n%d unique URLs, %d days covered" % (len(rows), len(per_day)))
    day = START
    while day <= END:
        print("%s\t%d" % (day.isoformat(), per_day.get(day.isoformat(), 0)))
        day += datetime.timedelta(days=1)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
