#!/usr/bin/env python3
"""mehrnews.com (Mehr News Agency, Iran) URL lister, 2026-09-25..2026-10-25.

Route: robots.txt is permissive (only /search is disallowed) and names a
per-day sitemap index in the *Persian* calendar:
    https://www.mehrnews.com/sitemap/1405/sitemap.xml  (sitemapindex)
  -> https://www.mehrnews.com/sitemap/1405/MM/DD/sitemap.xml  (one urlsets per Jalali day)

Each daily file holds ~900-1000 <url> entries with <loc> and <lastmod> (UTC).
The publication date is the Jalali day of the file the article first appears
in, mapped to Gregorian.  Verified: 1405/07/08 file -> lastmod 2026-09-30 and
the article page's JSON-LD datePublished 2026-09-30T20:29:48Z.
"""
import sys
import re
import datetime
import urllib.parse
from collections import defaultdict

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

OUT = "data/urls_custom/mehrnews-com.tsv"

# Jalali month lengths for year 1405 (months 1-6: 31, 7-11: 30, 12: 29/30).
J_MONTH_LEN = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
J_YEAR = 1405
# Anchor verified from the site: Jalali 1405/07/08 == Gregorian 2026-09-30.
ANCHOR_J = (7, 8)
ANCHOR_G = datetime.date(2026, 9, 30)

BASE = "https://www.mehrnews.com/sitemap/%d/%02d/%02d/sitemap.xml"


def jplus(jm, jd, n):
    """Return (month, day) n Jalali days after (jm, jd) in year 1405."""
    y, m, d = J_YEAR, jm, jd
    step = 1 if n >= 0 else -1
    for _ in range(abs(n)):
        d += step
        if d < 1:
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            d = J_MONTH_LEN[m - 1]
        elif d > J_MONTH_LEN[m - 1]:
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
    return m, d


def day_files():
    """Yield (jalali_m, jalali_d, gregorian_date) for the window +/- 2 days."""
    lo = (START - ANCHOR_G).days - 2
    hi = (END - ANCHOR_G).days + 2
    for n in range(lo, hi + 1):
        jm, jd = jplus(ANCHOR_J[0], ANCHOR_J[1], n)
        yield jm, jd, ANCHOR_G + datetime.timedelta(days=n)


URL_RE = re.compile(r"<loc>(.*?)</loc>")
ID_RE = re.compile(r"/news/(\d+)")
PHOTO_ID_RE = re.compile(r"/photo/(\d+)")


def main():
    # url -> earliest gregorian date it was listed under (article id keyed)
    seen = {}          # key -> (date, url)
    day_counts = defaultdict(int)
    ok_files = 0
    for jm, jd, gdate in day_files():
        url = BASE % (J_YEAR, jm, jd)
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print("SKIP %s status=%s" % (url, status), file=sys.stderr)
            continue
        locs = URL_RE.findall(text)
        if not locs:
            print("EMPTY %s" % url, file=sys.stderr)
            continue
        ok_files += 1
        for loc in locs:
            loc = loc.strip()
            if "mehrnews.com/news/" not in loc:
                continue
            m = ID_RE.search(loc)
            if not m:
                continue
            # Persian slugs: raw UTF-8 in <loc> fails to fetch, so write the
            # percent-encoded form (verified 200 + matching datePublished).
            loc = urllib.parse.quote(loc, safe=":/?&=#%")
            key = "n" + m.group(1)
            if key in seen:
                continue
            seen[key] = (gdate, loc)
        print("day %s (jalali %02d/%02d): %d URLs -> %d unique articles so far"
              % (gdate, jm, jd, len(locs), len(seen)), file=sys.stderr)

    rows = []
    for key, (gd, loc) in seen.items():
        if START <= gd <= END:
            rows.append((loc, gd))
            day_counts[gd] += 1

    # de-duplicate on the URL string itself as well
    uniq = {}
    for loc, gd in rows:
        if loc not in uniq:
            uniq[loc] = gd
    out = sorted(uniq.items(), key=lambda kv: (kv[1], kv[0]))

    with open(OUT, "w", encoding="utf-8") as f:
        for loc, gd in out:
            f.write("%s\t%s\n" % (loc, gd.isoformat()))

    print("files fetched ok: %d" % ok_files)
    d = START
    while d <= END:
        print("%s\t%d" % (d.isoformat(), day_counts.get(d, 0)))
        d += datetime.timedelta(days=1)
    print("TOTAL %d unique URLs written to %s" % (len(out), OUT))


if __name__ == "__main__":
    main()
