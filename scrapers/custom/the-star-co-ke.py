#!/usr/bin/env python3
"""The Star (Kenya) the-star.co.ke: list article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, Allow: /) advertises no sitemaps, but /sitemap_index.xml
exists and lists 50 numbered article chunks /articles/sitemap/N.xml (N=1 newest,
60 URLs each, ~1-2 days of publication per chunk). Walk N ascending and stop once
a chunk's newest date is before the window start.

Date = the YYYY-MM-DD in the URL slug (e.g. /news/2026-10-25-...), which the site
states and which matches the page's JSON-LD datePublished (verified:
/news/2026-10-25-sakaja-... -> datePublished 2026-10-25T21:20:00+0300). Fallback
to sitemap lastmod for URLs without a slug date. lastmod alone is not used because
it is edit time (chunk 1 held a 2026-10-25 article with lastmod 2026-10-26).
"""
import collections
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.the-star.co.ke"
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"
OUT = "data/urls_custom/the-star-co-ke.tsv"
SLUG_DATE = re.compile(r"/(20\d\d-\d\d-\d\d)-")

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_index(text):
    root = ET.fromstring(text)
    out = []
    for sm in root.findall("s:sitemap", NS):
        loc = sm.findtext("s:loc", default="", namespaces=NS).strip()
        if loc:
            out.append(loc)
    return out


def parse_chunk(text):
    """Yield (url, slug_date_or_None, lastmod) per entry."""
    root = ET.fromstring(text)
    for url in root.findall("s:url", NS):
        loc = url.findtext("s:loc", default="", namespaces=NS).strip()
        lm = url.findtext("s:lastmod", default="", namespaces=NS).strip()[:10]
        if not loc:
            continue
        m = SLUG_DATE.search(loc)
        yield loc, (m.group(1) if m else None), lm


def main():
    status, text, _ = fetch(BASE + "/sitemap_index.xml")
    if status != 200 or not text:
        sys.exit(f"sitemap_index.xml failed: status {status}")
    chunks = [u for u in parse_index(text) if "/articles/sitemap/" in u]
    # number them so we walk newest -> oldest
    numbered = []
    for u in chunks:
        m = re.search(r"/articles/sitemap/(\d+)\.xml", u)
        if m:
            numbered.append((int(m.group(1)), u))
    numbered.sort()

    urls = {}  # url -> date
    for n, u in numbered:
        status, text, _ = fetch(u)
        if status != 200 or not text:
            print(f"chunk {n}: status {status}, skipping", file=sys.stderr)
            continue
        entries = list(parse_chunk(text))
        if not entries:
            continue
        dates = [d or lm for (_, d, lm) in entries if d or lm]
        newest = max(dates) if dates else None
        oldest = min(dates) if dates else None
        print(f"chunk {n}: {len(entries)} urls, {oldest} .. {newest}")
        for loc, slug_d, lm in entries:
            date = slug_d or lm
            if date and WIN_START <= date <= WIN_END and loc not in urls:
                urls[loc] = date
        # walk newest->oldest: stop once this whole chunk is older than the window
        if newest and newest < WIN_START:
            print(f"chunk {n} fully before window; stopping")
            break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for loc in sorted(urls, key=lambda u: (urls[u], u)):
            f.write(f"{loc}\t{urls[loc]}\n")

    per_day = collections.Counter(urls.values())
    print(f"wrote {len(urls)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"  {d}\t{per_day[d]}")


if __name__ == "__main__":
    main()
