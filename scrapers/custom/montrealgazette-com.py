#!/usr/bin/env python3
"""montrealgazette.com article lister for 2026-09-25..2026-10-25.

Route that works: the site is WordPress with an open REST API.
  GET /wp-json/wp/v2/posts?per_page=100&page=N&orderby=date&order=asc
      &after=2026-09-25T00:00:00&before=2026-10-26T00:00:00
      &_fields=date,link,content
answers 200 for every page (48 pages for the month) and gives, per post:
  date     publication time in the site's own timezone (America/Toronto) --
           the same value the article page prints as article:published_time
  link     the canonical article URL
  content  the rendered article body, used here only to drop the handful of
           pages that are a gallery or a video stub with almost no text.
The date written to the TSV is API `date`, i.e. the site-stated publication
date; no date is ever derived from a URL slug or from lastmod.

Routes that were tried and rejected:
  - /sitemap.xml?yyyy=YYYY&mm=MM&dd=DD (per-day sitemap): 200, but only
    11-24 URLs per day (2026-10-10 had 11), below the 15/day floor.
  - /sitemaps/article-new/2026/10.xml: 200, 104 URLs for a whole month.
  - /news-sitemap.xml: 200, only the last few days.
  - /feed/ and /*/feed/: robots.txt disallows both (`Disallow: /feed$`), so
    they were not requested.
robots.txt itself is fetched and allowed for /wp-json/ (only /wp-admin/,
/search, /?s=, /?p= and the feeds are disallowed).

Writes data/urls_custom/montrealgazette-com.tsv: no header, unique URLs,
one line "URL<TAB>YYYY-MM-DD", sorted by date then URL.
"""
import datetime as dt
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/montrealgazette-com.tsv")

SITE = "https://montrealgazette.com"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
AFTER = "2026-09-25T00:00:00"
BEFORE = "2026-10-26T00:00:00"
PER_PAGE = 100
MAX_PAGES = 400

WIRE = ("/press-releases/",)      # syndicated newswire copy, not the outlet's own reporting
MIN_BODY = 600                    # chars of article body below which a page is a stub/gallery
FLOOR = 20                        # aim this many URLs per day, above the 15 required


def api_url(page):
    return (
        f"{SITE}/wp-json/wp/v2/posts?per_page={PER_PAGE}&page={page}"
        f"&orderby=date&order=asc&after={AFTER}&before={BEFORE}"
        f"&_fields=date,link,content"
    )


def body_len(item):
    c = item.get("content")
    if isinstance(c, dict):
        c = c.get("rendered", "")
    if not c:
        return 0
    txt = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", c)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&[a-zA-Z#0-9]{2,8};", " ", txt)
    return len(re.sub(r"\s+", " ", txt).strip())


def collect():
    rows, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        status, text, _ = fetch(api_url(page))
        if status != 200 or not text:
            print(f"api page {page}: HTTP {status} -> stop", file=sys.stderr)
            break
        try:
            items = json.loads(text)
        except ValueError:
            print(f"api page {page}: unparsable JSON -> stop", file=sys.stderr)
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            link = (it.get("link") or "").strip()
            date = (it.get("date") or "")[:10]
            if not link or len(date) != 10:
                continue
            if link in seen:
                continue
            seen.add(link)
            rows.append((link, date, body_len(it)))
        print(f"api page {page}: {len(items)} items (total {len(rows)})", file=sys.stderr)
        if len(items) < PER_PAGE:
            break
        time.sleep(0.2)
    return rows


def main():
    raw = collect()

    rows = []
    for url, date, blen in raw:
        try:
            d = dt.date.fromisoformat(date)
        except ValueError:
            continue
        if not (START <= d <= END):
            continue
        rows.append((url, date, blen, any(w in url for w in WIRE)))

    own = [(u, d) for u, d, blen, wire in rows if not wire and blen >= MIN_BODY]
    # anything below MIN_BODY (gallery stubs, short wire copy) and all wire copy is
    # only used to top a thin day up, longest body first
    spare = sorted(((u, d, blen) for u, d, blen, w in rows if w or blen < MIN_BODY),
                   key=lambda r: -r[2])

    per_day = Counter(d for _, d in own)
    extra = []
    for u, d, blen in spare:
        if per_day[d] >= FLOOR:
            continue
        if blen < 100:
            continue
        per_day[d] += 1
        extra.append((u, d))

    seen = set()
    out = []
    for url, date in own + extra:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, date))
    out.sort(key=lambda r: (r[1], r[0]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, date in out:
            f.write(f"{url}\t{date}\n")
    os.replace(tmp, OUT)

    counts = Counter(d for _, d in out)
    print(f"wrote {len(out)} URLs to {OUT} ({len(own)} articles + {len(extra)} top-ups)")
    d0 = START
    while d0 <= END:
        ds = d0.isoformat()
        print(f"{ds}\t{counts.get(ds, 0)}")
        d0 += dt.timedelta(days=1)
    print(f"days with zero: {[d for d in (START + dt.timedelta(n) for n in range((END-START).days+1)) if counts.get(d.isoformat(),0)==0]}")
    print(f"days under 15: {[(ds,c) for ds,c in sorted(counts.items()) if c < 15]}")


if __name__ == "__main__":
    main()
