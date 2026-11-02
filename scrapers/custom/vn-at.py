#!/usr/bin/env python3
"""vorarlberger nachrichten (vn.at) - article urls 2026-09-25 .. 2026-10-25.

route: robots.txt (www.vn.at) is permissive (Allow: /, Crawl-delay 1) but names
/wp-sitemap.xml which 404s, and the site is a nuxt SPA on www.vn.at, so the
public archive/sitemap/feed routes are all 404 (/sitemap.xml, /sitemap_index.xml,
/feed/, /news-sitemap.xml, /archiv, /wp-json on www).

the editorial backend however is a plain wordpress reachable at
api-nordstern.vn.at (found in the www.vn.at homepage html), whose robots.txt only
disallows /wp-admin/ and whose /wp-json/wp/v2/posts answers 200 with every post.
`date` there is site-local (Europe/Vienna) publish time and equals the page's
JSON-LD datePublished (checked on samples). `link` carries the article path
/<ressort>/YYYY/MM/DD/<slug>.vn on the api host; swapping the host to
https://www.vn.at gives the live article (200, full text + JSON-LD).

fallback (only if the REST api stops answering): the nuxt per-day section archive
https://www.vn.at/vorarlberg/YYYY/MM/DD, which returns 200 and links the same
article paths.

writes data/urls_custom/vn-at.tsv  (URL<TAB>YYYY-MM-DD, no header, unique urls).
"""
import json
import re
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = ROOT + "/data/urls_custom/vn-at.tsv"

WINDOW = (date(2026, 9, 25), date(2026, 10, 25))
API = "https://api-nordstern.vn.at/wp-json/wp/v2/posts"
PUBLIC = "https://www.vn.at"


def daterange():
    d = WINDOW[0]
    while d <= WINDOW[1]:
        yield d
        d += timedelta(days=1)


def in_window(iso):
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return d if WINDOW[0] <= d <= WINDOW[1] else None


def public_url(link):
    """https://api-nordstern.vn.at/vn/2026/10/20/slug.vn -> https://www.vn.at/vn/2026/10/20/slug.vn"""
    path = re.sub(r"^https?://[^/]+", "", link or "")
    if not path.startswith("/"):
        return None
    return PUBLIC + path


# ---------------------------------------------------------------- route 1: REST
def from_rest(pairs):
    after = (WINDOW[0] - timedelta(days=2)).isoformat() + "T00:00:00"
    before = (WINDOW[1] + timedelta(days=2)).isoformat() + "T00:00:00"
    total = 0
    for page in range(1, 61):
        url = (API + "?per_page=100&page=%d&orderby=date&order=asc"
               "&_fields=date,link" % page)
        url += "&after=" + after + "&before=" + before
        try:
            status, body, _ = fetch(url)
        except Exception as exc:  # network hiccup: stop, keep what we have
            print("REST page %d failed: %r" % (page, exc))
            break
        if status != 200 or not body:
            print("REST page %d status %s (stop)" % (page, status))
            break
        try:
            items = json.loads(body)
        except ValueError:
            print("REST page %d unparsable (stop)" % page)
            break
        if not items:
            break
        for it in items:
            d = in_window(it.get("date"))
            u = public_url(it.get("link"))
            if d and u:
                pairs.append((u, d))
        total += len(items)
        if len(items) < 100:
            break
    print("REST posts seen: %d" % total)
    return total


# ------------------------------------------------- route 2: per-day archive page
DAY_LINK = re.compile(r'href="(/([a-z0-9\-]+)/2026/(\d{2})/(\d{2})/[^"?#]+\.vn)"')


def from_day_pages(pairs):
    got = 0
    for d in daterange():
        url = "%s/vorarlberg/%s" % (PUBLIC, d.isoformat())
        try:
            status, body, _ = fetch(url)
        except Exception:
            continue
        if status != 200 or not body:
            continue
        seen = set()
        for m in DAY_LINK.finditer(body):
            path, mm, dd = m.group(1), m.group(3), m.group(4)
            if mm != d.strftime("%m") or dd != d.strftime("%d"):
                continue
            u = PUBLIC + path
            if u in seen:
                continue
            seen.add(u)
            pairs.append((u, d))
        got += len(seen)
    print("day-page links: %d" % got)
    return got


def main():
    pairs = []
    n = from_rest(pairs)
    have = len({p[0] for p in pairs})
    if have < 400:  # REST thin or dead -> add the per-day archive
        print("REST gave %d urls, falling back to day pages" % have)
        from_day_pages(pairs)

    seen = {}
    for u, d in pairs:
        if u not in seen:
            seen[u] = d

    rows = sorted(((u, d) for u, d in seen.items()), key=lambda r: (r[1], r[0]))
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d.isoformat()))
    print("wrote %d urls to %s" % (len(rows), OUT))

    per = {}
    for _, d in rows:
        per[d] = per.get(d, 0) + 1
    for d in daterange():
        print("%s\t%d" % (d.isoformat(), per.get(d, 0)))
    print("days covered: %d/31, min %d" % (
        len(per), min(per.values()) if per else 0))


if __name__ == "__main__":
    main()
