#!/usr/bin/env python3
"""Custom scraper for Kanal 5 (North Macedonia), kanal5.com.mk.

Route (verified 2026-10-26):
  1. https://kanal5.com.mk/robots.txt -> 200, "Disallow:" (empty = permissive),
     "Sitemap: https://kanal5.com.mk/sitemap.aspx"
  2. https://kanal5.com.mk/sitemap.aspx -> 200, one flat <urlset> with 10,000
     article URLs of the form https://kanal5.com.mk/<slug>/a<NNNN> plus ~43
     section pages. lastmod values run back to 2026-07-23, so the full
     2026-09-25..2026-10-25 window is covered by this single file.
  3. <lastmod> is the PUBLICATION date/time (site-local CET), not edit time:
     verified minute-for-minute against the date the article pages print in
     their "Објавил:" line, e.g. a769543: lastmod 2026-09-30T14:49:00+02:00
     vs page "30 септември 2026, 14:49"; a769445: lastmod 2026-10-10T19:17:41
     vs page "10 октомври 2026, 19:17".
Article pages carry the full story text (checked ~11.5k visible chars on a
sample), so URLs pass the 1500-char text check.

Output: data/urls_custom/kanal5-com-mk.tsv, lines "URL<TAB>YYYY-MM-DD",
unique URLs, dates from the sitemap lastmod, filtered to the window.
"""

import os
import re
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

SITE = "https://kanal5.com.mk"
SITEMAP = SITE + "/sitemap.aspx"
WINDOW_START = "2026-09-25"
WINDOW_END = "2026-10-25"
ARTICLE_RE = re.compile(r"/a\d+$")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "data", "urls_custom", "kanal5-com-mk.tsv")


def fetch_with_retry(url, tries=3, delay=5):
    last = None
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
            if status == 200 and text:
                return status, text
            last = "status %s (len %s)" % (status, len(text or ""))
        except Exception as e:  # network / robots hiccups
            last = repr(e)
        if i < tries - 1:
            time.sleep(delay * (i + 1))
    raise RuntimeError("failed to fetch %s after %d tries: %s" % (url, tries, last))


def main():
    status, text = fetch_with_retry(SITEMAP)
    if status != 200:
        raise RuntimeError("sitemap status %s" % status)

    root = ET.fromstring(text)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    rows = {}  # url -> date
    for e in root.findall("s:url", ns):
        loc = e.findtext("s:loc", None, ns)
        lm = e.findtext("s:lastmod", None, ns)
        if not loc or not lm:
            continue
        if not ARTICLE_RE.search(loc):
            continue  # keep only real articles, drop section pages
        day = lm[:10]
        if not (WINDOW_START <= day <= WINDOW_END):
            continue
        rows.setdefault(loc, day)  # unique URLs

    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(rows):
            f.write("%s\t%s\n" % (url, rows[url]))

    per_day = {}
    for d in rows.values():
        per_day[d] = per_day.get(d, 0) + 1
    total = 0
    for day in sorted(per_day):
        print("%s %d" % (day, per_day[day]))
        total += per_day[day]
    print("total %d unique URLs written to %s" % (total, OUT))


if __name__ == "__main__":
    main()
