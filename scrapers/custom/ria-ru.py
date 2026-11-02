#!/usr/bin/env python3
"""List RIA Novosti (ria.ru) article URLs published 2026-09-25..2026-10-25.

Route: ria.ru/robots.txt (200, permissive; only *-print.html, /search/, etc.
disallowed, `page=` params explicitly allowed) -> robots' sitemap index
https://ria.ru/sitemap_article_index.xml -> per-range article sitemaps
https://ria.ru/sitemap_article.xml?date_start=YYYYMMDD&date_end=YYYYMMDD.

One such request for the full window returns every article in the range
(24,571 for this window, verified live). Each <loc> is
https://ria.ru/YYYYMMDD/<slug>-<id>.html; the YYYYMMDD path segment is the
site's own publication date (shown on the article page). <lastmod> agrees on
the date for ~97.5% of entries; the mismatches are later edits (lastmod
strictly LATER than the path date), so the path date is used as the listed
date and lastmod is kept only as a sanity fallback when a loc has no date in
its path.
"""
import datetime as dt
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT = "data/urls_custom/ria-ru.tsv"

DATE_IN_PATH = re.compile(r"ria\.ru/(\d{8})/")


def parse_urlset(xml, seen):
    """Yield (url, date) from a urlset; date from path, lastmod fallback."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc_m = re.search(r"<loc>([^<]+)</loc>", block)
        lm_m = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        if not loc_m:
            continue
        loc, lm = loc_m.group(1), (lm_m.group(1) if lm_m else None)
        if loc in seen:
            continue
        m = DATE_IN_PATH.search(loc)
        if m:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        elif lm:
            d = dt.date.fromisoformat(lm[:10])
        else:
            continue
        out.append((loc, d))
        seen.add(loc)
    return out


def main():
    seen = set()
    items = []

    # Primary: one sitemap covering the whole window.
    url = f"https://ria.ru/sitemap_article.xml?date_start={START:%Y%m%d}&date_end={END:%Y%m%d}"
    status, text, _ = fetch(url)
    if status == 200 and text:
        items = parse_urlset(text, seen)

    # Fallback: monthly sitemaps from the robots index (if the range request
    # ever changes behaviour).
    if len(items) < 1000:
        idx_url = "https://ria.ru/sitemap_article_index.xml"
        i_status, i_text, _ = fetch(idx_url)
        if i_status == 200 and i_text:
            for loc in re.findall(r"<loc>([^<]+)</loc>", i_text):
                m = re.search(r"date_start=(\d{8})&date_end=(\d{8})", loc)
                if not m:
                    continue
                a = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
                b = dt.datetime.strptime(m.group(2), "%Y%m%d").date()
                if b < START or a > END:
                    continue
                s, t, _ = fetch(loc)
                if s == 200 and t:
                    items.extend(parse_urlset(t, seen))

    rows = {}
    for url, d in items:
        if START <= d <= END:
            rows[url] = d

    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(rows):
            f.write(f"{url}\t{rows[url]:%Y-%m-%d}\n")

    per_day = Counter(d for d in rows.values())
    for day in sorted(per_day):
        print(f"{day:%Y-%m-%d}\t{per_day[day]}")
    print(f"TOTAL\t{len(rows)}")


if __name__ == "__main__":
    main()
