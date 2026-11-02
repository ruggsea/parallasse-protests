#!/usr/bin/env python3
"""PTI (Press Trust of India) - https://www.ptinews.com

Route: robots.txt (permissive, only /editor-detail/ disallowed) names two sitemaps.
/sitemap.xml is a small static page list (lastmod 2023-2024, useless).
/news-sitemap.xml is a sitemapindex that lists only the newest ~2 per-day
Google-News urlset files, but the files themselves are served for ANY date:

    https://www.ptinews.com/sitemaps/pti-sitemap-YYYY-MM-DD.xml

Each urlset has one <url> per story with <loc> and
<news:publication_date>2026-09-30T23:57:01+05:30</news:publication_date>.
That publication date is the site's own statement -> the listed date is its
date part (IST, as the site writes it). 31 requests cover the window.

Output: data/urls_custom/ptinews-com.tsv  (URL<TAB>YYYY-MM-DD, no header)
"""
import os
import re
import sys
from collections import Counter

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = os.path.join(ROOT, "data", "urls_custom", "ptinews-com.tsv")
SITEMAP = "https://www.ptinews.com/sitemaps/pti-sitemap-%s.xml"

START = "2026-09-25"
END = "2026-10-25"

URL_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*(https?://[^\]<\s]+)")
DATE_RE = re.compile(r"<news:publication_date>\s*(?:<!\[CDATA\[)?\s*(\d{4}-\d{2}-\d{2})")


def window_days():
    import datetime
    d0 = datetime.date.fromisoformat(START)
    d1 = datetime.date.fromisoformat(END)
    d = d0
    while d <= d1:
        yield d.isoformat()
        d += datetime.timedelta(days=1)


def parse_day(text):
    """Yield (url, date) from one per-day news urlset, keeping <url> blocks aligned."""
    out = []
    for block in text.split("<url>")[1:]:
        mu = URL_RE.search(block)
        if not mu:
            continue
        md = DATE_RE.search(block)
        if not md:
            continue
        url = mu.group(1).strip()
        out.append((url, md.group(1)))
    return out


def main():
    rows = []
    seen = set()
    per_day = {}
    got_days = []
    missing = []
    for day in window_days():
        url = SITEMAP % day
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network trouble: remember and move on
            print("day %s ERROR %s" % (day, exc), flush=True)
            missing.append(day)
            continue
        if status != 200 or not text:
            print("day %s http %s (skip)" % (day, status), flush=True)
            missing.append(day)
            continue
        pairs = parse_day(text)
        got_days.append(day)
        n_day = 0
        for u, d in pairs:
            if d != day:
                # a urlset may hold the tail of the previous day; trust the stamp
                continue
            if not (START <= d <= END):
                continue
            if u in seen:
                continue
            seen.add(u)
            rows.append((u, d))
            n_day += 1
        per_day[day] = n_day
        print("day %s: %d urls" % (day, len(pairs)), flush=True)

    rows.sort(key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d))
    os.replace(tmp, OUT)

    counts = Counter(d for _, d in rows)
    print("\nwrote %d unique urls to %s" % (len(rows), OUT))
    print("days fetched: %d/31, missing: %s" % (len(got_days), missing or "none"))
    for d in sorted(counts):
        print("  %s\t%d" % (d, counts[d]))
    if not rows:
        return 1
    print("span %s .. %s" % (min(counts), max(counts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
