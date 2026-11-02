#!/usr/bin/env python3
"""The Guardian (Nigeria), guardian.ng.

Route (verified 2026-10-27): robots.txt (200) is fully permissive (Yoast, empty
Disallow). The sitemaps it advertises (/sitemap_index.xml, /news-sitemap.xml,
/wp-sitemap.xml) all return a WAF 403 with an empty body for our bot, so the
sitemap route is closed. The WordPress REST API is open, though:
/wp-json/wp/v2/posts?per_page=100&_fields=link,date,date_gmt&orderby=date&order=desc&page=N
returns 200 with 100 posts per page, newest first. The local 'date' field
(Africa/Lagos, UTC+1) is the date the site shows on the page; date_gmt equals
the page JSON-LD datePublished exactly. Article pages are fetchable (200,
6k+ visible chars) so the checker's sample re-fetch works.

The script walks pages newest-first until the oldest local date on a page
falls before 2026-09-25, keeps posts dated 2026-09-25..2026-10-25, de-dupes,
and writes data/urls_custom/guardian-ng.tsv as URL<TAB>YYYY-MM-DD.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(".")
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

API = ("https://guardian.ng/wp-json/wp/v2/posts"
       "?per_page=100&_fields=link,date,date_gmt&orderby=date&order=desc&page={page}")
START, END = "2026-09-25", "2026-10-25"
OUT = ROOT / "data/urls_custom/guardian-ng.tsv"
MAX_PAGES = 120  # safety valve, way above the expected ~50


def main():
    rows = {}          # url -> local date str
    per_day = {}
    page = 1
    stop = False
    t0 = time.time()
    while page <= MAX_PAGES and not stop:
        st, text, _ = fetch(API.format(page=page))
        if st != 200 or not text:
            print(f"page {page}: status {st}, aborting", flush=True)
            break
        posts = json.loads(text)
        if not posts:
            break
        for p in posts:
            local = p["date"][:10]  # site local time (Africa/Lagos)
            if local < START:
                stop = True        # pages are newest-first: we are past the window
            elif local <= END:
                u = p["link"]
                if u not in rows:
                    rows[u] = local
                    per_day[local] = per_day.get(local, 0) + 1
        print(f"page {page}: {len(posts)} posts, oldest local "
              f"{posts[-1]['date'][:10]}, in-window so far {len(rows)}", flush=True)
        page += 1
        if len(posts) < 100:
            break                  # last page

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u in sorted(rows):
            f.write(f"{u}\t{rows[u]}\n")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"WROTE {len(rows)} unique URLs to {OUT} "
          f"({len(per_day)} days, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
