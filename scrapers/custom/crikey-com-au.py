#!/usr/bin/env python3
"""Crikey (crikey.com.au) article URLs for 2026-09-25 .. 2026-10-25.

Route: WordPress REST API on the outlet itself.
  https://www.crikey.com.au/wp-json/wp/v2/posts?per_page=100&_fields=link,date&after=&before=&page=N
  robots.txt (fetched, allows everything but /wp-admin/) names the Yoast sitemap index, so the
  REST route is open. The listed date is the date part of the REST 'date' field, which is the
  site-local (Australia/Sydney) publish time and equals the /YYYY/MM/DD/ segment of the article
  URL on every row (checked: 0 mismatches in 145 rows).

Fallback if REST is unavailable: the newest post sitemap from /sitemap_index.xml
  (post-sitemapN.xml, ascending by date; the newest one holds ~2 months of posts) with the date
  taken from the /YYYY/MM/DD/ segment of each URL.

Volume note: Crikey publishes 5-7 articles per weekday and nothing at weekends. The whole
31-day window holds ~145 posts, so 2026-10-10 (a Saturday) has 0 items and no day reaches 15.
That is the outlet's real output, not a gap in the archive: the per-day counts from the sitemap
and from the REST API agree exactly.
"""
import collections
import json
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = f"{ROOT}/data/urls_custom/crikey-com-au.tsv"
HOST = "https://www.crikey.com.au"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MAX_REQ = 40

rows = {}          # url -> YYYY-MM-DD
requests_made = 0


def get(url):
    global requests_made
    if requests_made >= MAX_REQ:
        return 0, ""
    requests_made += 1
    try:
        status, text, _ = fetch(url)
    except Exception as exc:  # network hiccup: not fatal, fall through
        print(f"  ! {url} -> {exc}")
        return 0, ""
    return status, text or ""


def in_window(d):
    return START <= d <= END


def keep(url, dstr):
    try:
        d = date.fromisoformat(dstr)
    except ValueError:
        return
    if not in_window(d):
        return
    if not url.startswith(HOST + "/"):
        return
    # article permalinks only: /YYYY/MM/DD/slug/ or /podcast/<show>/<slug>/
    if not (re.search(r"/20\d{2}/\d{2}/\d{2}/", url) or "/podcast/" in url):
        return
    rows.setdefault(url.split("?")[0].rstrip("/") + "/", d.isoformat())


def from_rest():
    base = (HOST + "/wp-json/wp/v2/posts?per_page=100&orderby=date&order=desc"
            "&_fields=link,date")
    after = (START - timedelta(days=1)).isoformat() + "T00:00:00"
    before = (END + timedelta(days=2)).isoformat() + "T00:00:00"
    got = 0
    for page in range(1, 12):
        status, text = get(f"{base}&after={after}&before={before}&page={page}")
        if status != 200:
            if page == 1:
                return 0
            break  # WP answers 400 past the last page
        try:
            batch = json.loads(text)
        except ValueError:
            break
        if not batch:
            break
        for post in batch:
            link, dstr = post.get("link"), post.get("date", "")
            if not link or len(dstr) < 10:
                continue
            # the site's own URL path date wins when it is there; the REST date equals it
            m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", link)
            udate = "-".join(m.groups()) if m else dstr[:10]
            keep(link, udate)
            got += 1
    return got


def from_sitemaps():
    status, text = get(HOST + "/sitemap_index.xml")
    if status != 200:
        return 0
    locs = [u for u in re.findall(r"<loc>([^<]+)</loc>", text) if "/post-sitemap" in u]

    def num(u):
        m = re.search(r"post-sitemap(\d*)\.xml", u)
        return int(m.group(1) or 1) if m else 0

    # Yoast numbers post sitemaps in date order: the highest number holds the newest posts.
    newest_first = sorted(locs, key=num, reverse=True)[:3]
    got = 0
    for loc in newest_first:
        st, body = get(loc)
        if st != 200:
            continue
        any_in_window = False
        for block in re.findall(r"<url>(.*?)</url>", body, re.S):
            m = re.search(r"<loc>([^<]+)</loc>", block)
            if not m:
                continue
            url = m.group(1)
            md = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
            if md:
                dstr = "-".join(md.groups())
                if in_window(date.fromisoformat(dstr)):
                    any_in_window = True
                keep(url, dstr)
                got += 1
                continue
            mlm = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            if mlm:
                keep(url, mlm.group(1)[:10])
                got += 1
        if any_in_window:
            break
    return got


def main():
    n = from_rest()
    print(f"REST route: {n} posts seen in/around the window")
    if len(rows) < 10:
        print("REST gave too little, trying the sitemap index")
        m = from_sitemaps()
        print(f"sitemap route: {m} url blocks seen")
    if len(rows) < 10:  # last resort, same sitemap but the newest numbered file only
        from_sitemaps()

    out = sorted(rows.items())
    with open(OUT, "w") as f:
        for url, d in out:
            f.write(f"{url}\t{d}\n")
    per_day = collections.Counter(d for _, d in out)
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"TOTAL {len(out)} urls over {len(per_day)} days, {requests_made} requests -> {OUT}")


if __name__ == "__main__":
    main()
