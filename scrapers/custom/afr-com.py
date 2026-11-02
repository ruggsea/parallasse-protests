#!/usr/bin/env python3
"""Australian Financial Review (afr.com) article URL lister for a fixed date window.

Route: www.afr.com/robots.txt advertises a sitemap index
    https://www.afr.com/sitemaps/afr-sitemaps-articles.xml
which lists one flat urlset PER PUBLICATION DAY:
    https://www.afr.com/sitemaps/afr-articles-YYYYMMDD.xml
Each entry is <url><lastmod>YYYY-MM-DDTHH:MM:SS+11:00</lastmod><loc>...</loc></url>
and <lastmod> is the publication timestamp in Sydney time (verified against the
page's own JSON-LD datePublished: the page reports the same instant in UTC, e.g.
lastmod 2026-10-10T03:18:20+11:00 == datePublished 2026-10-09T16:18:20Z).
So the listed date is the date part of <lastmod>.

31 day files cover the window, so no recursion and no per-article fetching is
needed. Day files are fetched directly even if the index lags (they are served
independently), and every day is retried once.

Output: data/urls_custom/afr-com.tsv, one line "URL<TAB>YYYY-MM-DD", deduped.
"""
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "afr-com.tsv"

INDEX = "https://www.afr.com/sitemaps/afr-sitemaps-articles.xml"
DAY = "https://www.afr.com/sitemaps/afr-articles-%s.xml"

START, END = "2026-09-25", "2026-10-25"


def window_days():
    """All YYYYMMDD strings of the window, in order."""
    import datetime

    d0 = datetime.date.fromisoformat(START)
    d1 = datetime.date.fromisoformat(END)
    out = []
    d = d0
    while d <= d1:
        out.append(d.strftime("%Y%m%d"))
        d += datetime.timedelta(days=1)
    return out


def get(url, tries=3, pause=4):
    last = None
    for i in range(tries):
        try:
            status, text, _path = fetch(url)
        except Exception as exc:  # network hiccup, never fatal
            status, text = 0, None
            last = repr(exc)
        if status == 200 and text:
            return status, text
        last = status
        if status == -1:  # robots.txt disallows: no point retrying
            return status, None
        time.sleep(pause * (i + 1))
    return last, None


def parse_day(xml, day):
    """Return [(url, date)] for one day sitemap."""
    rows = []
    for block in re.findall(r"(?s)<url>(.*?)</url>", xml):
        m_loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
        if not m_loc:
            continue
        m_lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
        date = None
        if m_lm:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", m_lm.group(1))
            if m:
                date = m.group(1)
        if date is None:
            # no lastmod: fall back to the YYYYMMDD code in the article URL
            m = re.search(r"-(\d{8})-p\d+", m_loc.group(1))
            if m:
                date = "%s-%s-%s" % (m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:])
            else:
                date = "%s-%s-%s" % (day[:4], day[4:6], day[6:])
        if START <= date <= END:
            rows.append((m_loc.group(1), date))
    return rows


def main():
    status, idx = get(INDEX)
    listed = set()
    if idx:
        listed = {d for d in re.findall(r"afr-articles-(\d{8})\.xml", idx)}
    # always try every day of the window: the day files are served on their own
    # even when the index has not been refreshed yet (and the index is huge)
    wanted = window_days()

    found = {}
    failed = []
    for day in wanted:
        status, xml = get(DAY % day)
        if not xml:
            failed.append((day, status))
            continue
        for url, date in parse_day(xml, day):
            if url not in found:
                found[url] = date

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(((u, d) for u, d in found.items()), key=lambda r: (r[1], r[0]))
    with open(OUT, "w") as fh:
        for url, date in rows:
            fh.write("%s\t%s\n" % (url, date))

    counts = Counter(d for _, d in rows)
    print("wrote %d URLs to %s" % (len(rows), OUT))
    for day in wanted:
        iso = "%s-%s-%s" % (day[:4], day[4:6], day[6:])
        print("  %s  %d" % (iso, counts.get(iso, 0)))
    if failed:
        print("failed days: %s" % failed)


if __name__ == "__main__":
    main()
