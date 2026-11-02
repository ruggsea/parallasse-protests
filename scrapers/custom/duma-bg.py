#!/usr/bin/env python3
"""List duma.bg article URLs published 2026-09-25..2026-10-25.

Route: the "all news" list ?go=news&p=list&categoryId=0&page=N is a strictly
descending-by-publication-time archive of the whole site (~26-30 items/page).
Each item carries its publication time in <time datetime="YYYY-MM-DD HH:MM:SS">
and the article URL is /<slug>-nNNNNNN. Walk pages newest-first until the
oldest item on a page predates the window start. robots.txt is 404 on
duma.bg (nothing to ask), so this route is open.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.duma.bg"
WINDOW_START = "2026-09-25"
WINDOW_END = "2026-10-25"
MAX_PAGES = 120

ITEM = re.compile(r'<time datetime="(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}"')
SLUG = re.compile(r'href="([a-z0-9\-]+n\d{6})"')


def page_items(page):
    """Return [(date, url), ...] from one listing page."""
    s, t, _ = fetch("%s/?go=news&p=list&categoryId=0&page=%d" % (BASE, page))
    if s != 200 or not t:
        print("page %d -> status %s, stopping" % (page, s))
        return None
    out = []
    for m in ITEM.finditer(t):
        seg = t[max(0, m.start() - 3000):m.start()]
        slugs = SLUG.findall(seg)
        if slugs:
            out.append((m.group(1), BASE + "/" + slugs[-1]))
    return out


def main():
    found = {}  # url -> date
    for page in range(1, MAX_PAGES + 1):
        items = page_items(page)
        if items is None or not items:
            break
        dates = [d for d, _ in items]
        for d, u in items:
            if WINDOW_START <= d <= WINDOW_END:
                found.setdefault(u, d)
        oldest = min(dates)
        newest = max(dates)
        print("page %d: %d items, %s .. %s (in-window so far: %d)" % (
            page, len(items), oldest, newest, len(found)))
        if oldest < WINDOW_START:
            break
    # write TSV
    outpath = "data/urls_custom/duma-bg.tsv"
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w") as f:
        for u in sorted(found):
            f.write("%s\t%s\n" % (u, found[u]))
    per = Counter(found[u] for u in found)
    print("total unique URLs: %d" % len(found))
    for d in sorted(per):
        print("%s: %d" % (d, per[d]))


if __name__ == "__main__":
    main()
