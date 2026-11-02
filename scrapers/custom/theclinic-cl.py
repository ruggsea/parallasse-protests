#!/usr/bin/env python3
"""The Clinic (theclinic.cl, Chile) — article URL lister for 2026-09-25..2026-10-25.

Route: robots.txt advertises https://www.theclinic.cl/sitemap_index.xml (Yoast).
It lists 195 numbered post sitemaps (/post-sitemap.xml = 1, /post-sitemap195.xml
= newest), 1000 <url> entries each with <loc> and <lastmod>.  We walk them from
the newest downwards and stop when a sitemap's dates fall entirely before the
window.

Date: the day permalink /YYYY/MM/DD/ in every article URL, which is the site's
own publication date (verified against article:published_time on page samples).
<lastmod> is only a fallback for a URL without a day permalink.
"""

import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.theclinic.cl"
INDEX = BASE + "/sitemap_index.xml"
OUT = "data/urls_custom/theclinic-cl.tsv"
START = "2026-09-25"
END = "2026-10-25"

DAY_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
URL_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
ITEM_RE = re.compile(
    r"<url>\s*<loc>\s*(.*?)\s*</loc>\s*(?:<lastmod>\s*(.*?)\s*</lastmod>)?", re.S
)


def get(url, tries=4):
    """Fetch with retries; polite_fetch already rate-limits and logs."""
    last = (0, "")
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup
            last = (0, "")
            print("  ! %s %s" % (url, exc), file=sys.stderr)
        else:
            if status == 200 and text:
                return status, text
            last = (status, text or "")
        time.sleep(2 + 3 * i)
    return last


def sitemap_numbers(index_xml):
    """Return post-sitemap URLs ordered newest first."""
    urls = [u for u in URL_RE.findall(index_xml) if re.search(r"/post-sitemap\d*\.xml$", u)]

    def num(u):
        m = re.search(r"/post-sitemap(\d*)\.xml$", u)
        return int(m.group(1)) if m and m.group(1) else 1

    return sorted(urls, key=num, reverse=True)


def main():
    found = {}  # url -> date

    status, idx = get(INDEX)
    if status == 200 and "<loc>" in idx:
        smaps = sitemap_numbers(idx)
    else:
        # Fallback: probe numbering directly from the newest downwards.
        print("index unusable (status %s); probing sitemap numbers" % status, file=sys.stderr)
        smaps = []
        for n in range(230, 150, -1):
            cand = "%s/post-sitemap%d.xml" % (BASE, n)
            st, tx = get(cand, tries=1)
            if st == 200 and "<loc>" in tx:
                smaps.append(cand)

    print("post sitemaps to walk: %d" % len(smaps), file=sys.stderr)

    walked = []
    for smap in smaps:
        walked.append(smap)
        st, tx = get(smap)
        if st != 200 or "<loc>" not in tx:
            print("  skip %s (status %s)" % (smap, st), file=sys.stderr)
            continue
        items = ITEM_RE.findall(tx)
        if not items:
            items = [(u, "") for u in URL_RE.findall(tx)]
        dates = []
        for loc, lastmod in items:
            lastmod = (lastmod or "").strip()
            m = DAY_RE.search(loc)
            if m:
                date = "%s-%s-%s" % m.groups()
            elif re.match(r"\d{4}-\d{2}-\d{2}", lastmod):
                date = lastmod[:10]
            else:
                continue
            dates.append(date)
            if START <= date <= END:
                found[loc.strip()] = date
        lo = min(dates) if dates else ""
        hi = max(dates) if dates else ""
        print("  %s: %d urls, dates %s..%s, kept so far %d"
              % (smap.rsplit("/", 1)[-1], len(items), lo, hi, len(found)), file=sys.stderr)
        # Sitemaps are ordered by publication, oldest first inside each file, so
        # the newest dates of a file older than the window mean every following
        # file is entirely older too.  A single recently-updated old post must
        # not stop the walk, hence max() and not min().
        if hi and hi < START:
            print("  next sitemaps all predate the window, stopping", file=sys.stderr)
            break
        if len(walked) >= 12:  # ~1 month per file; a hard stop for safety
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for url, date in rows:
            fh.write("%s\t%s\n" % (url, date))

    per_day = Counter(d for _, d in rows)
    print("wrote %d unique URLs to %s" % (len(rows), OUT))
    for date in sorted(per_day):
        print("  %s\t%d" % (date, per_day[date]))
    missing = [d for d in ("2026-09-30", "2026-10-10", "2026-10-20") if per_day.get(d, 0) < 15]
    if missing:
        print("WARNING: thin days: %s" % ", ".join(missing), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
