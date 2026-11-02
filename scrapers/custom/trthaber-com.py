#!/usr/bin/env python3
"""TRT Haber (trthaber.com) article URL lister for 2026-09-25..2026-10-25.

Route: robots.txt is permissive (only /arama.html and /haber/hava-durumu/ disallowed)
and advertises /sitemaps/news.xml, a sitemapindex of per-month Google-news style
urlsets /sitemaps/news-YYYY-MM.xml. Each <url> carries <loc> (CDATA) and
<lastmod> which is the publish instant in +03:00 (verified equal to the page's
JSON-LD datePublished, same day and same minute on samples). Two month files
(2026-09, 2026-10) cover the whole window.

Listed date = date part of the sitemap <lastmod> (Europe/Istanbul local clock, which
is what the site's own JSON-LD states), which the page's datePublished confirms.
"""
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.trthaber.com"
OUT = "data/urls_custom/trthaber-com.tsv"
START = "2026-09-25"
END = "2026-10-25"

# robots.txt disallows these paths; never list them.
DISALLOW = ("/arama.html", "/haber/hava-durumu/")


def months_between(start, end):
    y0, m0 = int(start[:4]), int(start[5:7])
    y1, m1 = int(end[:4]), int(end[5:7])
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def parse_urlset(text):
    """Yield (loc, lastmod) from a flat urlset (loc may be CDATA-wrapped)."""
    for block in re.findall(r"<url>(.*?)</url>", text, re.S):
        m = re.search(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^\]<]+?)\s*(?:\]\]>)?\s*</loc>", block, re.S)
        if not m:
            continue
        loc = m.group(1).strip()
        lm = re.search(r"<lastmod>\s*([0-9T:+\-\.Z]+)\s*</lastmod>", block)
        if not lm:
            continue
        yield loc, lm.group(1)


def main():
    rows = {}
    for ym in months_between(START, END):
        url = f"{BASE}/sitemaps/news-{ym}.xml"
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup: try the next month file
            print(f"WARN {url} raised {exc}", file=sys.stderr)
            continue
        print(f"{url} -> {status} {len(text)} bytes", file=sys.stderr)
        if status != 200:
            continue
        for loc, lastmod in parse_urlset(text):
            day = lastmod[:10]
            if not (START <= day <= END):
                continue
            if any(p in loc for p in DISALLOW):
                continue
            if not loc.startswith(BASE + "/haber/"):
                continue
            if not loc.endswith(".html"):
                continue
            rows.setdefault(loc, day)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for loc, day in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            fh.write(f"{loc}\t{day}\n")
    os.replace(tmp, OUT)

    counts = {}
    for day in rows.values():
        counts[day] = counts.get(day, 0) + 1
    for day in sorted(counts):
        print(f"{day}\t{counts[day]}")
    print(f"TOTAL {len(rows)} urls -> {OUT}")


if __name__ == "__main__":
    main()
