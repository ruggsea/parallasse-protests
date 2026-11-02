#!/usr/bin/env python3
"""La Voz del Interior (lavoz.com.ar) article URLs for a date window.

Route: the site's own reverse-chronological listing /lo-ultimo/N/ (canonical
/ultimas-noticias/).  Each page is a Next.js page whose __NEXT_DATA__ JSON carries
pageProps.matchConfig.content: 20 story objects with the fields "url" and
"publishedDate" (the date the site states for the story, site-local -03:00).
Walk N = 1, 2, 3 ... until three consecutive pages are entirely older than the
window start, keep every story whose date falls inside the window.

Everything is fetched through polite_fetch (robots.txt + per-host rate limit).
Writes data/urls_custom/lavoz-com-ar.tsv as "URL<TAB>YYYY-MM-DD", no header.
"""
import json
import os
import re
import sys
import time

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = os.path.join(ROOT, "data/urls_custom/lavoz-com-ar.tsv")
BASE = "https://www.lavoz.com.ar/lo-ultimo/"
START = "2026-09-25"
END = "2026-10-25"
MAX_PAGES = 600
NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def page_url(n):
    return BASE if n == 1 else "%s%d/" % (BASE, n)


def parse_page(text):
    """-> list of (url, 'YYYY-MM-DD') from the listing page's __NEXT_DATA__."""
    m = NEXT_RE.search(text or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    props = (data.get("props") or {}).get("pageProps") or {}
    content = ((props.get("matchConfig") or {}).get("content")) or []
    out = []
    for item in content:
        url = item.get("url") or ""
        date = (item.get("publishedDate") or "")[:10]
        if url.startswith("/") and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            out.append(("https://www.lavoz.com.ar" + url.split("?")[0], date))
    return out


def main():
    found = {}
    stale = 0
    pages = 0
    for n in range(1, MAX_PAGES + 1):
        status, text, _ = fetch(page_url(n), cache=False)
        if status != 200:
            # one retry, then give up on this page but keep going a little
            time.sleep(3)
            status, text, _ = fetch(page_url(n), cache=False)
        if status != 200:
            print("page %d: HTTP %s" % (n, status), file=sys.stderr)
            stale += 1
            if stale >= 3:
                break
            continue
        pages += 1
        items = parse_page(text)
        if not items:
            print("page %d: no items parsed, stopping" % n, file=sys.stderr)
            break
        for url, date in items:
            if START <= date <= END and url not in found:
                found[url] = date
        newest = max(d for _, d in items)
        if newest < START:
            stale += 1
            if stale >= 3:
                break
        else:
            stale = 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, date in rows:
            f.write("%s\t%s\n" % (url, date))
    os.replace(tmp, OUT)

    per_day = {}
    for url, date in rows:
        per_day[date] = per_day.get(date, 0) + 1
    print("pages read: %d   urls: %d   -> %s" % (pages, len(rows), OUT))
    for date in sorted(per_day):
        print("%s\t%d" % (date, per_day[date]))


if __name__ == "__main__":
    main()
