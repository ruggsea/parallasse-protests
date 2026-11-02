#!/usr/bin/env python3
"""ottawacitizen.com (Postmedia WordPress) — articles published 2026-09-25..2026-10-25.

Two routes, unioned (both are the site's own statements of date):

1. WordPress REST (primary, exact publication dates):
     /wp-json/wp/v2/posts?per_page=100&_fields=link,date,date_gmt
       &after=2026-09-23T00:00:00&before=2026-10-27T00:00:00&page=N
   robots.txt disallows /wp-admin/ and /*? but the REST query URLs are not
   matched by those rules; the fetch went through (status 200).
   Listed date = date-part of 'date' (site-local America/Toronto publish time,
   not 'modified').  Verified == page JSON-LD datePublished on spot checks.

2. Per-day story sitemaps (supplement + fallback), one per day:
     /sitemap-story.xml?y=YYYY&m=M&d=D   (explicitly Allowed in robots.txt)
   These carry <loc>+<lastmod>; they also list occasional /feature/ long reads
   that the posts endpoint does not return.  For a URL the REST pass did not
   return, the listed date is the date-part of <lastmod> when that falls inside
   the window, otherwise the sitemap's own day.

Cross-check run on 2026-10-26: the two routes agreed on 30 of 31 days
(09-30: 12 vs 12, 10-10: 6 vs 6, 10-20: 17 vs 17), the only differences being
the three /feature/ pages the sitemaps add.  So the outlet really does publish
fewer than 15 articles on some days (see notes: low_volume).
"""
import sys, re, json, collections, datetime, os

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

OUT = "data/urls_custom/ottawacitizen-com.tsv"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://ottawacitizen.com/wp-json/wp/v2/posts"
SITEMAP = "https://ottawacitizen.com/sitemap-story.xml"
PER_PAGE = 100
MAX_PAGES = 50


def get(url, tries=3):
    """polite_fetch with a few retries on transient failures. None on give-up."""
    for _ in range(tries):
        try:
            status, text, _path = fetch(url)
        except Exception:
            status, text = 0, None
        if status == 200 and text:
            return text
        if status == -1:            # robots disallow: route closed, do not retry
            return None
        if status in (0, 429, 500, 502, 503, 504):
            continue
        return None
    return None


def window_days():
    d = START
    while d <= END:
        yield d
        d += datetime.timedelta(days=1)


def rest_pass(seen):
    for page in range(1, MAX_PAGES + 1):
        url = (f"{BASE}?per_page={PER_PAGE}&_fields=link,date,date_gmt"
               f"&after=2026-09-23T00:00:00&before=2026-10-27T00:00:00&page={page}")
        text = get(url)
        if not text:
            return
        try:
            items = json.loads(text)
        except ValueError:
            return
        if not isinstance(items, list) or not items:
            return
        for it in items:
            link = (it.get("link") or "").strip()
            date = (it.get("date") or it.get("date_gmt") or "")[:10]
            if not link or len(date) != 10:
                continue
            try:
                d = datetime.date.fromisoformat(date)
            except ValueError:
                continue
            if START <= d <= END:
                seen.setdefault(link, date)
        dates = [it.get("date", "")[:10] for it in items if it.get("date")]
        if len(items) < PER_PAGE or (dates and min(dates) < "2026-09-23"):
            return


def sitemap_pass(seen):
    """Fill in URLs the REST pass missed; also the whole list if REST returned nothing."""
    for day in window_days():
        ds = day.isoformat()
        text = get(f"{SITEMAP}?y={day.year}&m={day.month}&d={day.day}")
        if not text:
            continue
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.S)
        mods = re.findall(r"<lastmod>\s*(.*?)\s*</lastmod>", text, re.S)
        for i, loc in enumerate(locs):
            loc = loc.strip()
            if not loc or loc in seen:
                continue
            date = ds
            if i < len(mods):
                cand = mods[i].strip()[:10]
                try:
                    cd = datetime.date.fromisoformat(cand)
                except ValueError:
                    cd = None
                if cd and START <= cd <= END:
                    date = cand
            seen[loc] = date


def main():
    seen = {}
    rest_pass(seen)
    rest_count = len(seen)
    sitemap_pass(seen)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = collections.Counter(seen.values())
    with open(OUT, "w") as f:
        for link in sorted(seen, key=lambda u: (seen[u], u)):
            f.write(f"{link}\t{seen[link]}\n")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"REST-only\t{rest_count}")
    print(f"TOTAL\t{len(seen)}")


if __name__ == "__main__":
    main()
