#!/usr/bin/env python3
"""rg.ru (Rossiyskaya Gazeta) article URLs for 2026-09-25..2026-10-25.

Route: robots.txt (permissive, UA * only blocks /printable/ and */.html) points to
https://rg.ru/sitemaps/index.xml, a sitemap index of PER-DAY urlsets keyed by
date_start/date_end unix timestamps that are MSK (UTC+3) midnights. Each day's
urlset lists that day's articles; article URLs embed the publication date in the
path (/YYYY/MM/DD/slug.html) and the page JSON-LD datePublished + visible date
div match it exactly (verified on samples). <lastmod> is edit time, NOT
publication time, so the listed date is taken from the URL path.
"""
import datetime
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://rg.ru/sitemaps/index.xml"
WINDOW_START = "2026-09-25"
WINDOW_END = "2026-10-25"
OUT = Path("data/urls_custom/rg-ru.tsv")
MSK = datetime.timezone(datetime.timedelta(hours=3))

LOC_RE = re.compile(r"<loc>(.*?)</loc>")
PAIR_RE = re.compile(r"<loc>(.*?)</loc>.*?<lastmod>(.*?)</lastmod>", re.S)
PATHDATE_RE = re.compile(r"rg\.ru/(\d{4})/(\d{2})/(\d{2})/")


def msk_midnight(d: str) -> int:
    return int(datetime.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=MSK).timestamp())


def main() -> None:
    start, end = WINDOW_START, WINDOW_END
    w0, w1 = msk_midnight(start), msk_midnight(end) + 86400  # window in MSK

    status, index, _ = fetch(BASE)
    if status != 200:
        raise SystemExit(f"sitemap index fetch failed: status={status}")
    index = html.unescape(index)

    # Per-day entries whose range touches the window, plus a 1-day margin each side
    lo, hi = w0 - 86400, w1 + 86400
    entries = []
    for m in re.finditer(
        r"index\.xml\?date_start=(\d+)&date_end=(\d+)", index
    ):
        a, b = int(m.group(1)), int(m.group(2))
        if a < hi and b > lo:
            entries.append((a, b))
    entries.sort()
    print(f"per-day sitemap entries to fetch: {len(entries)}", flush=True)

    urls = {}  # url -> date string
    for a, b in entries:
        day = datetime.datetime.fromtimestamp(a, MSK).strftime("%Y-%m-%d")
        status, body, _ = fetch(f"{BASE}?date_start={a}&date_end={b}")
        if status != 200:
            print(f"  {day}: sitemap fetch status={status}, skipped", flush=True)
            continue
        n = 0
        for loc, lastmod in PAIR_RE.findall(body):
            m = PATHDATE_RE.search(loc)
            if not m:
                continue  # non-dated paths (evergreen/section pages) are not dated news
            d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if w0 <= msk_midnight(d) < w1:
                if loc not in urls:
                    urls[loc] = d
                    n += 1
        print(f"  {day}: +{n} new in-window article urls (file total ok)", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    per_day = {}
    with OUT.open("w", encoding="utf-8") as f:
        for url in sorted(urls):
            d = urls[url]
            f.write(f"{url}\t{d}\n")
            per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(urls)} unique urls to {OUT}")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")


if __name__ == "__main__":
    main()
