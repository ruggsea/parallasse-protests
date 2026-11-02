#!/usr/bin/env python3
"""ubs.mn (UBS, Mongolia) — article URLs for the 2026-09-25 .. 2026-10-25 window.

Route (verified 2026-10-27):
  robots.txt is permissive (Allow: /) and names one sitemap: https://ubs.mn/sitemap.xml
  That sitemap is a single flat <urlset> (1405 <url>), no index, no recursion needed.
  In-window articles are the date-slug ones: /news/YYYY/MM/DD/<slug>/ whose <lastmod>
  is the publication date (day-precision) and equals the page's own
  JSON-LD "datePublished" and its <time datetime="...">.

Everything else on that sitemap is the legacy numeric archive (/news/16200/ ...), whose
pages carry "datePublished": null and <time datetime=""> — they cannot be dated, so they
are deliberately excluded rather than guessed at.

Fallbacks kept for robustness if the sitemap ever goes stale or 5xx:
  * paged listing /news/page/N/ (cards carry a "YYYY.MM.DD" kicker)
  * RSS /feed.xml (<pubDate>)
Each article's listed date is cross-checked: URL path date, else lastmod, else kicker/feed.
"""

import re
import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://ubs.mn"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "data", "urls_custom", "ubs-mn.tsv")

DATE_SLUG = re.compile(r"^/news/(\d{4})/(\d{2})/(\d{2})/[^/]+/?$")
KICKER = re.compile(r'class="kicker">(?:<span[^>]*>[^<]*</span>)?\s*(\d{4})\.(\d{2})\.(\d{2})')


def get(url, tries=3):
    """Polite fetch with a couple of retries on transport/5xx trouble."""
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # noqa: BLE001
            status, text = 0, ""
            sys.stderr.write("fetch error %s: %r\n" % (url, exc))
        if status == 200 and text:
            return status, text
        if status in (403, 429, 500, 502, 503, 504, 0) and i + 1 < tries:
            continue
        return status, text or ""
    return status, text or ""


def in_window(d):
    return d is not None and START <= d <= END


def path_date(url):
    """Publication date carried by the article URL path, if any."""
    m = DATE_SLUG.match(url.replace(BASE, ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_iso(s):
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def collect_sitemap(found):
    """https://ubs.mn/sitemap.xml — flat urlset, lastmod is the publish date here."""
    status, text = get(BASE + "/sitemap.xml")
    print("sitemap.xml status=%s len=%d" % (status, len(text)))
    if status != 200:
        return
    n = 0
    for loc, lastmod in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S):
        loc = loc.strip()
        n += 1
        if not DATE_SLUG.match(loc.replace(BASE, "")):
            continue  # legacy numeric ids: undated pages, skipped on purpose
        d = path_date(loc) or parse_iso(lastmod)
        if not in_window(d):
            continue
        found.setdefault(loc, d)
    print("sitemap urls seen=%d kept=%d" % (n, len(found)))


def collect_listing(found, pages=40):
    """Fallback: paged 'all news' listing, cards carry a YYYY.MM.DD kicker."""
    seen_pages = 0
    for p in range(1, pages + 1):
        url = BASE + "/news/" if p == 1 else "%s/news/page/%d/" % (BASE, p)
        status, text = get(url, tries=2)
        if status != 200 or not text:
            print("listing %s status=%s stop" % (url, status))
            break
        seen_pages += 1
        oldest = None
        # walk card blocks so a card's link and its kicker stay together
        for block in re.split(r'<article class="card', text)[1:]:
            hrefs = re.findall(r'href="(/news/[^"]+)"', block)
            k = KICKER.search(block)
            for href in hrefs:
                if not DATE_SLUG.match(href.replace(BASE, "")):
                    continue
                d = path_date(href)
                if not in_window(d):
                    if d and oldest is None:
                        oldest = d
                    continue
                found.setdefault(BASE + href, d)
            if k:
                kd = date(int(k.group(1)), int(k.group(2)), int(k.group(3)))
                if oldest is None or kd < oldest:
                    oldest = kd
        if oldest is not None and oldest < START:
            break
    print("listing pages read=%d" % seen_pages)


def collect_feed(found):
    """Fallback: RSS /feed.xml (<pubDate> is a bare YYYY-MM-DD here)."""
    status, text = get(BASE + "/feed.xml", tries=2)
    print("feed.xml status=%s len=%d" % (status, len(text)))
    if status != 200:
        return
    for m in re.finditer(r"<item>(.*?)</item>", text, re.S):
        item = m.group(1)
        link = re.search(r"<link>(.*?)</link>", item)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", item)
        if not link:
            continue
        loc = link.group(1).strip()
        d = path_date(loc) or parse_iso(pub.group(1) if pub else "")
        if in_window(d) and DATE_SLUG.match(loc.replace(BASE, "")):
            found.setdefault(loc, d)


def main():
    found = {}
    try:
        collect_sitemap(found)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("sitemap step failed: %r\n" % exc)
    if len(found) < 10:
        try:
            collect_listing(found)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("listing step failed: %r\n" % exc)
    if len(found) < 10:
        try:
            collect_feed(found)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("feed step failed: %r\n" % exc)

    rows = sorted(((u, d) for u, d in found.items() if in_window(d)), key=lambda r: (r[1], r[0]))
    # one row per URL, newest first dated order kept simple: chronological
    seen = set()
    out_rows = []
    for u, d in rows:
        if u in seen:
            continue
        seen.add(u)
        out_rows.append((u, d))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for u, d in out_rows:
            fh.write("%s\t%s\n" % (u, d.isoformat()))
    os.replace(tmp, OUT)

    per_day = {}
    for _, d in out_rows:
        per_day[d] = per_day.get(d, 0) + 1
    print("wrote %d urls to %s" % (len(out_rows), OUT))
    day = START
    while day <= END:
        print("%s\t%d" % (day.isoformat(), per_day.get(day, 0)))
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
