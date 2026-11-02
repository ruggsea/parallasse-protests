#!/usr/bin/env python3
"""rtsh.al (RTSH - Radio Televizioni Shqiptar, Albania): article URLs 2026-09-25..2026-10-25.

Route (worked out 2026-10-25):
  robots.txt is the Yoast default block: "User-agent: * / Disallow:" (nothing disallowed) plus
  "Sitemap: https://rtsh.al/sitemap_index.xml". So every path is open.

  1. PRIMARY: the site's own WordPress REST API, one request per calendar day
       https://rtsh.al/wp-json/wp/v2/posts?per_page=100&page=N&_fields=id,date,link
              &orderby=date&order=asc&after=YYYY-MM-DDT00:00:00&before=<next day>T00:00:01
     `date` is the publication time in the site's own timezone, `link` is the article URL
     (JSON decode handles the escaped slashes WP emits). ~37 requests for the whole window,
     1 req/s through polite_fetch, so the run costs under a minute.
     The `before` boundary is pushed 1 s past midnight so a post stamped exactly 00:00:00 is
     not lost between two days; the date written is always the post's own `date`, and rows are
     deduped by URL, so the overlap cannot produce a wrong date.

  2. FALLBACK: Yoast post sitemaps (post-sitemap.xml, post-sitemapNNN.xml) from
     /sitemap_index.xml, taking <lastmod> as the date. Used only if the REST API yields almost
     nothing (a WAF or a disabled wp-json); ~5 fetches, since only the chunks whose own lastmod
     is after 2026-09-20 can hold posts from the window.

Why the REST route is the right one: on this site <lastmod> is the *modification* time, so the
sitemaps also contain old articles that were edited in the window (e.g. one published 2026-08-04,
edited 2026-10-13). Cross-checked on 2026-10-25: the sitemap chunks 112-115 hold 2606 URLs whose
lastmod falls in the window; the REST route returns 2603, exactly those minus two old-but-edited
posts and the homepage, and zero REST URLs are absent from the sitemaps. lastmod equals the
publication day on 2584 of those 2603 and is within one day on 2595. So the two routes agree and
the REST route is the more accurate of the two.

Not included: the /informacione/ entries (RTSH board decisions, a separate post type, ~317 pages
such as /informacione/vendim-nr-52-date-12-10-2026/) - they are regulatory documents, not articles.

Output: data/urls_custom/rtsh-al.tsv, one line "URL<TAB>YYYY-MM-DD", unique URLs, no header.
"""
import collections
import datetime
import json
import os
import re
import sys

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = os.path.join(ROOT, "data/urls_custom/rtsh-al.tsv")
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
API = "https://rtsh.al/wp-json/wp/v2/posts"
_failures = []


def log(msg):
    print(msg, flush=True)


def rest_window():
    """One request per day (+1 page when a day has more than 100 posts). -> {url: 'YYYY-MM-DD'}"""
    rows = {}
    day = START
    while day <= END:
        nxt = day + datetime.timedelta(days=1)
        page = 1
        while True:
            url = ("%s?per_page=100&page=%d&_fields=id,date,link&orderby=date&order=asc"
                   "&after=%sT00:00:00&before=%sT00:00:01"
                   % (API, page, day.isoformat(), nxt.isoformat()))
            status, text, _ = fetch(url)
            if status == 400:          # rest_post_invalid_page_number: past the last page
                break
            if status != 200:
                _failures.append((day.isoformat(), status))
                log("  ! %s page %d -> HTTP %s" % (day.isoformat(), page, status))
                break
            try:
                batch = json.loads(text)
            except ValueError:
                _failures.append((day.isoformat(), "bad-json"))
                break
            for post in batch:
                link = (post.get("link") or "").strip()
                date = (post.get("date") or "")[:10]
                if link and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                    rows.setdefault(link, date)
            if len(batch) < 100:
                break
            page += 1
        day = nxt
    return rows


def sitemap_window():
    """Fallback: post-sitemap chunks listed in the Yoast index, dated by <lastmod>."""
    rows = {}
    status, text, _ = fetch("https://rtsh.al/sitemap_index.xml")
    if status != 200 or not text:
        log("  ! sitemap index -> HTTP %s" % status)
        return rows
    chunks = []
    for loc, lastmod in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text):
        if "/post-sitemap" not in loc:
            continue
        if lastmod[:10] >= "2026-09-20":     # earlier chunks cannot hold window posts
            chunks.append(loc)
    for loc in chunks:
        status, text, _ = fetch(loc)
        if status != 200 or not text:
            log("  ! %s -> HTTP %s" % (loc, status))
            continue
        for u, lastmod in re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text):
            d = lastmod[:10]
            if START.isoformat() <= d <= END.isoformat():
                rows.setdefault(u.strip(), d)
        log("  fallback %s" % loc)
    return rows


def main():
    log("rtsh.al: %s .. %s" % (START, END))
    rows = rest_window()
    log("REST route: %d URLs" % len(rows))
    if len(rows) < 500:
        log("REST route gave too little, using the Yoast post sitemaps as well")
        for u, d in sitemap_window().items():
            rows.setdefault(u, d)
    # keep only what the site itself dates inside the window, dedupe by URL (dict already unique)
    clean = {}
    for u, d in rows.items():
        if not u.startswith("http"):
            continue
        if START.isoformat() <= d <= END.isoformat():
            clean[u] = d
    log("after window filter: %d unique URLs (%d dropped outside the window)"
        % (len(clean), len(rows) - len(clean)))
    if not clean:
        log("nothing collected, leaving the output untouched")
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for u in sorted(clean, key=lambda x: (clean[x], x)):
            f.write("%s\t%s\n" % (u, clean[u]))
    os.replace(tmp, OUT)

    per_day = collections.Counter(clean.values())
    log("wrote %s" % OUT)
    log("URLs per day:")
    for d in sorted(per_day):
        log("  %s  %3d" % (d, per_day[d]))
    log("total %d URLs on %d days" % (len(clean), len(per_day)))
    if _failures:
        log("failed requests: %s" % _failures[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
