#!/usr/bin/env python3
"""El Dinamo (eldinamo.cl) URL lister for 2026-09-25..2026-10-25.

Route: robots.txt (permissive, Disallow: /draft/ only) names three sitemaps.
The per-month content sitemaps at https://www.eldinamo.cl/_files/sitemaps/YYYY/MM.xml
contain every article with the publication date in the URL path
(/<section>/YYYY/MM/DD/<slug>/). Verified that the URL date equals the page
JSON-LD datePublished calendar date (Santiago time, -03:00). sitemap_news.xml
(Google News, only ~7 days back) is merged in as a cross-check; its
news:publication_date is used when present, URL path otherwise.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.eldinamo.cl/_files/sitemaps"
MONTHS = [f"{BASE}/2026/09.xml", f"{BASE}/2026/10.xml",
          f"{BASE}/sitemap_news.xml"]
START, END = "2026-09-25", "2026-10-25"
OUT = "data/urls_custom/eldinamo-cl.tsv"

DATE_PATH = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def date_from_path(url):
    m = DATE_PATH.search(url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def parse_urlset(text, use_news_date=False):
    """Yield (url, date) from a sitemap urlset body."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "news": "http://www.google.com/schemas/sitemap-news/0.9"}
    root = ET.fromstring(text)
    for u in root.findall("sm:url", ns):
        loc_el = u.find("sm:loc", ns)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        d = None
        if use_news_date:
            pd = u.find("news:news/news:publication_date", ns)
            if pd is not None and pd.text:
                d = pd.text.strip()[:10]
        if d is None:
            d = date_from_path(url)
        if d:
            yield url, d


def main():
    found = {}  # url -> date
    for src in MONTHS:
        status, text, _ = fetch(src)
        if status != 200 or not text:
            print(f"WARN {src} status={status}, skipping", flush=True)
            continue
        got = 0
        for url, d in parse_urlset(text, use_news_date="sitemap_news" in src):
            if START <= d <= END and d == (date_from_path(url) or d):
                if url not in found:
                    got += 1
                found[url] = found.get(url, d)
        print(f"{src}: +{got} new urls in window", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w", encoding="utf-8") as fh:
        for url in sorted(found):
            d = found[url]
            fh.write(f"{url}\t{d}\n")
            per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(found)} urls to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    if not per_day:
        sys.exit(1)


if __name__ == "__main__":
    main()
