#!/usr/bin/env python3
"""List El Financiero (Mexico) article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, permissive, names the sitemap index) ->
  /arc/outboundfeeds/sitemap-index/?outputType=xml
  which lists one sitemap PER DAY: /arc/outboundfeeds/sitemap*/YYYY-MM-DD/?outputType=xml.
The index covers 2017-09-02..today, so the whole window is present.
Each daily urlset lists that day's article URLs; every article URL carries the
publication date in its path (/section/YYYY/MM/DD/slug/), which equals the page
JSON-LD datePublished (verified: path 2026-10-20 == datePublished
2026-10-20T23:41:44.081Z on /entretenimiento/2026/10/20/...; page text 10k chars).
<lastmod> is Arc's record-update time, so it is NOT used as the date.
"""
import re
import sys
import datetime
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/elfinanciero-com-mx.tsv"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://www.elfinanciero.com.mx/arc/outboundfeeds/"
DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
LOC_RE = re.compile(r"<loc>(.*?)</loc>")


def main():
    st, idx, _ = fetch(BASE + "sitemap-index/?outputType=xml")
    if st != 200 or not idx:
        raise SystemExit(f"sitemap index failed: {st}")
    by_date = {}
    for loc in LOC_RE.findall(idx):
        m = re.search(r"/(\d{4}-\d{2}-\d{2})/", loc)
        if m:
            by_date[m.group(1)] = loc

    # List date = date in the URL path (site-stated publication date, == page
    # JSON-LD datePublished). A URL counts on its path date, not on which daily
    # sitemap happened to list it.
    found = {}  # path-date str -> set of urls
    missing = []
    d = START
    while d <= END:
        key = d.isoformat()
        url = by_date.get(key)
        if url is None:
            missing.append(key)
            d += datetime.timedelta(days=1)
            continue
        st, xml, _ = fetch(url)
        if st != 200 or not xml:
            missing.append(key + f" (status {st})")
            d += datetime.timedelta(days=1)
            continue
        for loc in LOC_RE.findall(xml):
            m = DATE_RE.search(loc)
            if not m:
                continue
            pd = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if not (START <= pd <= END):
                continue
            found.setdefault(pd.isoformat(), set()).add(loc)
        d += datetime.timedelta(days=1)

    rows = []
    seen = set()
    for key in sorted(found):
        for u in sorted(found[key]):
            if u in seen:
                continue
            seen.add(u)
            rows.append((u, key))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u, key in rows:
            f.write(f"{u}\t{key}\n")

    per_day = {k: len(v) for k, v in found.items()}
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    if missing:
        print("missing days:", missing)
    for k in sorted(per_day):
        print(k, per_day[k])
    if per_day:
        print("min/day:", min(per_day.values()))


if __name__ == "__main__":
    main()
