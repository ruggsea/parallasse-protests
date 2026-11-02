#!/usr/bin/env python3
"""Scrape Iraqi News Agency (ina.iq) article URLs for 2026-09-25 .. 2026-10-25.

Route: /ar/latest/ is the site-wide chronological "latest news" listing
(Smart Engine CMS). 12 items per page, strictly descending, paginated as
/ar/latest/page/N/. Each item block carries one <a href="https://ina.iq/ar/
<section>/<id>-slug.html"> and one <time class="date-element"> that is either
relative ("اليوم, HH:MM" = today, "أمس, HH:MM" = yesterday) or absolute
("DD-MM-YYYY, HH:MM") relative to the fetch date. robots.txt (200) has no
Sitemap line; /rss.xml is stale (May 2026) so the archive walk is the route.

Walk pages from 1 downward until a whole page is older than the window start.
"""
import datetime as dt
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
BASE = "https://ina.iq/ar/latest/"
OUT = "data/urls_custom/ina-iq.tsv"
MAX_PAGES = 900

ART_RE = re.compile(
    r'<a href="(https://ina\.iq/ar/[a-zA-Z\-\u0600-\u06FF%]+/\d+-[^"]*\.html)"'
)
TIME_RE = re.compile(r'<time class="date-element">([^<]+)</time>')
ABS_RE = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})\s*,\s*(\d{2}):(\d{2})")
REL_RE = re.compile(r"(اليوم|أمس)\s*,\s*(\d{2}):(\d{2})")


def parse_date(raw, today):
    """Return a dt.date from a date-element label, or None if unparseable."""
    m = ABS_RE.search(raw)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = REL_RE.search(raw)
    if m:
        off = 0 if m.group(1) == "اليوم" else 1
        return today - dt.timedelta(days=off)
    return None


def main():
    today = dt.date.today()
    found = {}          # url -> date
    skipped_no_date = 0
    pages = 0
    n = 1
    while n <= MAX_PAGES:
        url = BASE if n == 1 else f"{BASE}page/{n}/"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"page {n}: status {status}, stopping", flush=True)
            break
        pages = n
        blocks = re.split(r"<article", text)
        page_dates = []
        for block in blocks[1:]:
            a = ART_RE.search(block)
            if not a:
                continue
            u = a.group(1).split("?")[0]
            tm = TIME_RE.search(block)
            d = parse_date(tm.group(1), today) if tm else None
            if d is None:  # fall back to any absolute date in the block
                m = ABS_RE.search(block)
                if m:
                    d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if d is None:
                skipped_no_date += 1
                continue
            page_dates.append(d)
            if u not in found:
                found[u] = d
        if not page_dates:
            print(f"page {n}: no dated items, stopping", flush=True)
            break
        if all(d < START for d in page_dates):
            print(f"page {n}: whole page before window (oldest so far done), stopping", flush=True)
            break
        if n % 25 == 0:
            print(f"page {n}: {len(found)} urls, newest on page {max(page_dates)}, oldest {min(page_dates)}", flush=True)
        n += 1

    rows = []
    for u, d in found.items():
        if START <= d <= END:
            rows.append((u, d))
    rows.sort(key=lambda r: (r[1], r[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"\nWrote {len(rows)} URLs to {OUT} ({pages} pages fetched, {skipped_no_date} items without date)")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    for probe in (dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 20)):
        print(f"probe {probe}: {per_day.get(probe, 0)} urls")
    missing = [str(d) for d in range(START.toordinal(), END.toordinal() + 1) if dt.date.fromordinal(d) not in per_day]
    if missing:
        print("days with no urls: " + ", ".join(missing))
    else:
        print("all 31 days present")


if __name__ == "__main__":
    main()
