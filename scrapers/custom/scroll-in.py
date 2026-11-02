#!/usr/bin/env python3
"""List Scroll.in (scroll.in, India) article URLs published 2026-09-25 .. 2026-10-25.

Route: scroll.in's own JSON feed /feed/page/<N> (the infinite-scroll endpoint the
site's Vue bundle calls). Each page returns ~35-45 article objects with
'permalink' and 'published' (ISO 8601, site timezone +05:30). Pages are
newest-first, so we walk N = 1, 2, 3 ... until a page's newest item is older
than the window start.

Union with the site's own sitemaps (https://scroll.in/sitemap/sitemap.xml and
/news-sitemap.xml): both are rolling lists capped at 200 URLs covering roughly
the last 10 days, using <lastmod> == page JSON-LD datePublished; they catch any
article the feed paging might skip.

Everything goes through polite_fetch (robots.txt read first, 1 req/s per host,
logged). robots.txt for scroll.in disallows only /article/print/ and
/newsrepublic/, so all routes used here are allowed.
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = "data/urls_custom/scroll-in.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MAX_PAGES = 70          # hard cap on feed requests
ART_RE = re.compile(r"^https://scroll\.in/(?:article|latest|news|magazine|videos?)/\d+/[^?#]+$")


def walk_articles(obj, acc):
    """Collect every dict that looks like an article (has permalink)."""
    if isinstance(obj, dict):
        if "permalink" in obj and "published" in obj:
            acc.append(obj)
        for v in obj.values():
            walk_articles(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_articles(v, acc)
    return acc


def parse_iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def from_feed(rows, stats):
    prev_newest = None
    stale = 0
    for page in range(1, MAX_PAGES + 1):
        url = "https://scroll.in/feed/page/%d" % page
        status, text, _ = fetch(url)
        stats["requests"] += 1
        if status != 200 or not text:
            stats["feed_errors"].append("%s -> %s" % (url, status))
            break
        try:
            data = json.loads(text)
        except ValueError:
            stats["feed_errors"].append("%s -> bad json" % url)
            break
        arts = walk_articles(data, [])
        if not arts:
            break
        dts = [parse_iso(a.get("published", "")) for a in arts]
        dts = [d for d in dts if d]
        if not dts:
            break
        newest, oldest = max(dts), min(dts)
        for a in arts:
            d = parse_iso(a.get("published", ""))
            link = (a.get("permalink") or "").strip()
            if not d or not ART_RE.match(link):
                continue
            dd = d.date()
            if START <= dd <= END:
                rows[link] = dd
        if prev_newest is not None and newest > prev_newest + timedelta(days=1):
            stale += 1
        prev_newest = newest if prev_newest is None else max(prev_newest, newest)
        if newest.date() < START:
            stats["pages_walked"] = page
            break
        stats["pages_walked"] = page


def from_sitemaps(rows, stats):
    for sm in ("https://scroll.in/sitemap/sitemap.xml",
               "https://scroll.in/sitemap/news-sitemap.xml"):
        status, text, _ = fetch(sm)
        stats["requests"] += 1
        if status != 200 or not text:
            stats["sitemap_errors"].append("%s -> %s" % (sm, status))
            continue
        for block in re.findall(r"(?s)<url>(.*?)</url>", text):
            loc = re.search(r"<loc>\s*(\S+?)\s*</loc>", block)
            lm = (re.search(r"<lastmod>\s*([0-9T:+\-\.]+)\s*</lastmod>", block)
                  or re.search(r"<news:publication_date>\s*([0-9T:+\-\.]+)\s*<", block))
            if not loc or not lm:
                continue
            d = parse_iso(lm.group(1))
            link = loc.group(1).strip()
            if not d or not ART_RE.match(link):
                continue
            dd = d.date()
            if START <= dd <= END and link not in rows:
                rows[link] = dd


def main():
    rows = {}
    stats = {"requests": 0, "pages_walked": 0, "feed_errors": [], "sitemap_errors": []}
    try:
        from_feed(rows, stats)
    except Exception as e:  # never lose a good sitemap pass to a feed hiccup
        stats["feed_errors"].append("exception: %r" % (e,))
    try:
        from_sitemaps(rows, stats)
    except Exception as e:
        stats["sitemap_errors"].append("exception: %r" % (e,))

    with open(OUT, "w") as f:
        for link, dd in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write("%s\t%s\n" % (link, dd.isoformat()))

    per_day = {}
    for link, dd in rows.items():
        per_day[dd] = per_day.get(dd, 0) + 1
    d = START
    while d <= END:
        print("%s\t%d" % (d.isoformat(), per_day.get(d, 0)))
        d += timedelta(days=1)
    print("TOTAL %d URLs, %d days covered, %d requests, feed pages %d"
          % (len(rows), len(per_day), stats["requests"], stats["pages_walked"]))
    for k in ("feed_errors", "sitemap_errors"):
        if stats[k]:
            print(k, stats[k])


if __name__ == "__main__":
    main()
