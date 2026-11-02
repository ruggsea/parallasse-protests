#!/usr/bin/env python3
"""Frontline (India), frontline.thehindu.com -- article URLs 2026-09-25 .. 2026-10-25.

Route: robots.txt (https://frontline.thehindu.com/robots.txt, 200) advertises three
sitemaps. /sitemap/archive.xml is a <urlset> index of ONE per-day file per calendar
date, since 1997:
    https://frontline.thehindu.com/sitemap/archive/all/YYYYMMDD_1.xml
Each per-day file lists the articles the site published that day. Its <lastmod> is the
last-EDIT time (dateModified, drifts days), so the listed date is taken from the file's
own date -- the site's archive day -- not from lastmod.

Checked 2026-10-27:
  * 2 articles from /sitemap/archive/all/20261010_1.xml re-fetched: JSON-LD
    datePublished 2026-10-10T13:04:15+05:30 and 2026-10-10T15:22:20+05:30, i.e. exactly
    the file date; their dateModified is 2026-10-15, i.e. the lastmod in the file.
  * /sitemap/googlenews/all/all.xml (Google News sitemap, ~48h only) has
    <news:publication_date>: its 2026-10-26 items are exactly the 2026-10-26 day-file's
    items (5 = 5, 0 differences either way), so the day file is the complete publish
    list for a day.
  * /archive/web/YYYY/MM/DD/ day pages render the same 50 latest articles whatever day
    is asked for -- the day is not a filter there, unusable as a route.
  * /sitemap/update/all.xml only covers the last few days; googlenews only ~48h.

Volume is genuinely low: the outlet publishes ~2-13 items per calendar day, so
2026-09-30 (13), 2026-10-10 (8) and 2026-10-20 (8) are below 15. That is the site's real
output, not a missing archive: the Google News cross-check above shows no day-file item
is absent from the news sitemap on a day both cover.

Writes data/urls_custom/frontline-thehindu-com.tsv as "URL<TAB>YYYY-MM-DD", no header,
unique URLs, and prints the count per day.
"""
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = ROOT + "/data/urls_custom/frontline-thehindu-com.tsv"
BASE = "https://frontline.thehindu.com/sitemap/archive/all/%s_1.xml"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
# article pages end in .ece; drop section/index pages if a day file ever lists one
ART = re.compile(r"^https?://frontline\.thehindu\.com/.+/article\d+\.ece$")


def day_urls(d):
    """Return set of article URLs published on day d, per the site's day sitemap."""
    url = BASE % d.strftime("%Y%m%d")
    for attempt in range(3):
        status, text, _robots = fetch(url)
        if status == 200 and text:
            locs = LOC.findall(text)
            return {u for u in locs if ART.match(u)}, len(locs)
        if status == 404:
            return set(), 0          # no file for that day
        time.sleep(3 + 3 * attempt)  # 5xx / 429 / network: back off and retry
    print("FAILED %s %s" % (d, url), file=sys.stderr)
    return set(), -1


def main():
    found = {}          # url -> iso day (earliest day file it appears in)
    counts = {}
    missing = []
    for i in range((END - START).days + 1):
        d = START + timedelta(days=i)
        urls, nloc = day_urls(d)
        if nloc < 0:
            missing.append(d.isoformat())
            counts[d.isoformat()] = 0
            continue
        counts[d.isoformat()] = len(urls)
        for u in urls:
            found.setdefault(u, d.isoformat())

    rows = sorted(((u, day) for u, day in found.items()), key=lambda r: (r[1], r[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for u, day in rows:
            f.write("%s\t%s\n" % (u, day))

    print("wrote %d unique urls to %s" % (len(rows), OUT))
    for day in sorted(counts):
        print("  %s  %d" % (day, counts[day]))
    if missing:
        print("days with no sitemap answer: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
