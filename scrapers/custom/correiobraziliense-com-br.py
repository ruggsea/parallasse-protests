#!/usr/bin/env python3
"""Correio Braziliense (correiobraziliense.com.br) URL lister for a fixed window.

Route (robots.txt is permissive: only /busca/ disallowed):
  robots.txt advertises three sitemaps:
    /sitemap/map/day/sitemap.xml      -> flat urlset, but only the last ~6 days
    /sitemap/1.xml, /sitemap/2.xml    -> sitemapindexes of /sitemap/map/<N>.xml
  /sitemap/map/<N>.xml are flat urlsets of <=1000 URLs, ordered oldest->newest
  within the file, each URL carrying <lastmod> in -03:00 (Brazil local time).
  The highest N is the newest file (1385 at time of writing), so we walk N
  downwards until a file's oldest <lastmod> falls before the window start.
  One file covers roughly 4-6 days of publication, so ~8 files cover 31 days.

  Listed date = date part of <lastmod>. Verified against the pages' JSON-LD
  datePublished (see notes).

  /blogs-redirect/ URLs are dropped: they are 401-char redirect stubs whose own
  page date is 2020-08-07 regardless of the sitemap lastmod.
"""
import re
import sys
import time
import datetime as dt
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = f"{ROOT}/data/urls_custom/correiobraziliense-com-br.tsv"
HOST = "https://www.correiobraziliense.com.br"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)

SKIP_SUBSTR = ("/blogs-redirect/",)


def date_of(lastmod):
    """lastmod is like 2026-10-06T10:41:17-03:00 -> 2026-10-06 (already local)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lastmod or "")
    if not m:
        return None
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_urls(xml):
    """Return [(loc, date)] from a flat urlset."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        m = re.search(r"<loc>\s*(.*?)\s*</loc>", block, re.S)
        if not m:
            continue
        loc = m.group(1).strip()
        lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block, re.S)
        d = date_of(lm.group(1) if lm else "")
        if d is None:
            # Google-News style fallback
            pd = re.search(r"<news:publication_date>\s*(.*?)\s*</news:publication_date>", block, re.S)
            d = date_of(pd.group(1) if pd else "")
        out.append((loc, d))
    return out


def max_sitemap_number():
    st, t, _ = fetch(f"{HOST}/sitemap/2.xml")
    if st != 200 or not t:
        return None
    nums = [int(n) for n in re.findall(r"/sitemap/map/(\d+)\.xml", t)]
    return max(nums) if nums else None


def main():
    found = {}  # url -> date
    reqs = 0

    top = max_sitemap_number()
    reqs += 1
    print(f"sitemap index: highest N = {top}")
    if top is None:
        print("could not read the sitemap index", file=sys.stderr)
        top = 1385

    n = top
    misses = 0
    while n >= 1 and reqs < 60:
        url = f"{HOST}/sitemap/map/{n}.xml"
        st, t, _ = fetch(url)
        reqs += 1
        if st != 200 or not t or "<url>" not in t:
            print(f"  {n}.xml status={st} -> skip")
            misses += 1
            n -= 1
            if misses >= 4:
                break
            continue
        misses = 0
        rows = parse_urls(t)
        dates = [d for _, d in rows if d]
        if not dates:
            print(f"  {n}.xml no dates -> stop")
            break
        lo, hi = min(dates), max(dates)
        kept = 0
        for loc, d in rows:
            if d is None or not (START <= d <= END):
                continue
            if any(s in loc for s in SKIP_SUBSTR):
                continue
            if loc not in found:
                found[loc] = d
                kept += 1
        print(f"  {n}.xml st={st} urls={len(rows)} span={lo}..{hi} kept={kept} total={len(found)}")
        if lo < START:
            break
        n -= 1

    # safety net: the site's day sitemap (covers the last few days only)
    st, t, _ = fetch(f"{HOST}/sitemap/map/day/sitemap.xml")
    reqs += 1
    if st == 200 and t:
        rows = parse_urls(t)
        added = 0
        for loc, d in rows:
            if d is None or not (START <= d <= END):
                continue
            if any(s in loc for s in SKIP_SUBSTR):
                continue
            if loc not in found:
                found[loc] = d
                added += 1
        print(f"  day/sitemap.xml st={st} urls={len(rows)} added={added} total={len(found)}")
    else:
        print(f"  day/sitemap.xml status={st}")

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = Counter()
    with open(OUT, "w") as f:
        for loc in sorted(found, key=lambda u: (found[u], u)):
            f.write(f"{loc}\t{found[loc].isoformat()}\n")
            per_day[found[loc].isoformat()] += 1

    print(f"\nwrote {len(found)} urls to {OUT} in {reqs} requests")
    day = START
    while day <= END:
        print(f"  {day.isoformat()}\t{per_day.get(day.isoformat(), 0)}")
        day += dt.timedelta(days=1)
    for key in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"TARGET {key}: {per_day.get(key, 0)}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"elapsed {time.time() - t0:.1f}s")
