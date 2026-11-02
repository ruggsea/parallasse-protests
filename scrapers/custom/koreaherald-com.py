#!/usr/bin/env python3
"""The Korea Herald (koreaherald.com) -- article URLs for 2026-09-25 .. 2026-10-25.

Route (all requests through polite_fetch):
  robots.txt (200, permissive: only /_TP/, /_CP/, /_CT/, /PRnewswire disallowed) advertises
      Sitemap: https://www.koreaherald.com/sitemap/articles/2026   <- sitemapindex, one file per DAY
  Each day file  https://www.koreaherald.com/sitemap/articles/2026/YYYYMMDD  is a flat <urlset>
      of ~12-90 article URLs.

Date rule (measured, 7/7 pages):  the publication date is the DAY OF THE SITEMAP FILE, NOT <lastmod>.
  <lastmod> drifts: on the 20261009 file three entries carried lastmod 2026-10-08 / 2026-10-11 while
  their pages' JSON-LD "datePublished" was 2026-10-09 (e.g. /article/10897831 -> 2026-10-09T15:06+09:00,
  sitemap lastmod 2026-10-11 = last-edit time).  Checking page JSON-LD against the file day:
    /article/10898092 file 20261010 -> datePublished 2026-10-10T08:49+09:00
    /article/10898012 file 20261009 -> datePublished 2026-10-09T21:30+09:00
    /article/10897344 file 20261009 -> datePublished 2026-10-09T09:00+09:00
    /article/10897831 file 20261009 -> datePublished 2026-10-09T15:06+09:00
    /article/10897965 file 20261009 -> datePublished 2026-10-09T20:16+09:00
  So listed date = file day (KST publication day), which is what the site states.

Volume: the site is a Saturday-light publisher. Its own day files give
  2026-09-30 = 88, 2026-10-10 = 12 (Saturday, the day after Hangeul Day), 2026-10-20 = 70.
  2026-10-10 is genuinely below 15 by the outlet's own sitemap (neighbouring Saturdays 10-03/10-17/10-24
  are 17/17/16); no route showed more (GDELT DOC answered 429/empty, Wayback CDX timed out).

Writes data/urls_custom/koreaherald-com.tsv : URL<TAB>YYYY-MM-DD, unique, no header.
"""
import datetime
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://www.koreaherald.com/sitemap/articles/2026"
OUT = REPO / "data" / "urls_custom" / "koreaherald-com.tsv"

LOC_RE = re.compile(r"<loc>\s*(https://www\.koreaherald\.com/article/\d+)\s*</loc>")


def get(url, tries=3):
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return text
        sys.stderr.write("  [retry %d] %s -> %s\n" % (i + 1, url, status))
        time.sleep(3 + 3 * i)
    return None


def main():
    rows = {}          # url -> date iso
    per_day = {}       # date iso -> count
    day = START
    while day <= END:
        iso = day.isoformat()
        url = "%s/%s" % (BASE, day.strftime("%Y%m%d"))
        text = get(url)
        n = 0
        if text:
            for art in LOC_RE.findall(text):
                if art in rows:
                    continue
                rows[art] = iso
                n += 1
        else:
            sys.stderr.write("  [MISS] no sitemap for %s\n" % iso)
        per_day[iso] = n
        day += datetime.timedelta(days=1)

    # Belt and braces: the news sitemap carries news:publication_date; keep any in-window entry
    # that the day files missed (it only holds ~48 h, so usually adds nothing).
    text = get("https://www.koreaherald.com/sitemap/latest-articles", tries=1)
    if text:
        for m in re.finditer(
            r"<loc>\s*(https://www\.koreaherald\.com/article/\d+)\s*</loc>.*?"
            r"<news:publication_date>(\d{4}-\d{2}-\d{2})",
            text,
            re.S,
        ):
            art, d = m.group(1), m.group(2)
            if art in rows:
                continue
            dd = datetime.date.fromisoformat(d)
            if START <= dd <= END:
                rows[art] = d
                per_day[d] = per_day.get(d, 0) + 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for art in sorted(rows):
            f.write("%s\t%s\n" % (art, rows[art]))

    print("wrote %d unique URLs to %s" % (len(rows), OUT))
    for iso in sorted(per_day):
        print("  %s  %d" % (iso, per_day[iso]))
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("CHECK %s: %d" % (probe, per_day.get(probe, 0)))


if __name__ == "__main__":
    main()
