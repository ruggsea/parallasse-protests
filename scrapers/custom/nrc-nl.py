#!/usr/bin/env python3
"""nrc.nl (NRC, Netherlands) - article URLs 2026-09-25 .. 2026-10-25.

Route: robots.txt (fetched, allows /nieuws/ and /sitemap/; disallows /data/, /paywall-api/,
/search/, /preview/) -> sitemapindex https://www.nrc.nl/sitemap/index.xml -> per-month flat
urlsets https://www.nrc.nl/sitemap/2026-9.xml and /sitemap/2026-10.xml (one request each,
no recursion; the October file covers 10-01..today, the September file covers 09-01..09-30).
Each entry is <loc> + <changefreq> only (NO usable lastmod), and the publication date is the
date segment of the URL path /nieuws/YYYY/MM/DD/<slug>-a<id> - that is the site's own date,
and it agrees with the page's JSON-LD datePublished / trafilatura date.

Puzzles and cartoons are mixed into the same sitemaps (sudoku, crux, briljant, kamagurka,
fokke-sukke, ...). Their pages carry no article text (a puzzle widget), so they are dropped:
data-driven, a slug that appears on >= RECUR_DAYS distinct days inside the window is a
recurring puzzle/cartoon, plus a short explicit list for the daily/weekly ones.
Read-only, ~4 requests total, well under a minute.
"""
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = ROOT + "/data/urls_custom/nrc-nl.tsv"
START = "2026-09-25"
END = "2026-10-25"
UA_HOST = "https://www.nrc.nl"
RECUR_DAYS = 8          # same slug on this many days = recurring puzzle/cartoon
PUZZLE_SLUGS = {
    "briljant", "crux", "aan-zet", "koprol", "cijferblok", "woordzoeker", "cinco",
    "precies-vier", "vorto", "fokke-sukke", "sudoku", "scrypto", "kamagurka", "dante",
    "in-het-midden", "broeierige-blikken", "dag-van-de-leerkracht", "cryptogram",
    "kruiswoord", "puzzel", "strip", "cartoon", "tekening",
}

URL_RE = re.compile(r"/nieuws/(\d{4})/(\d{2})/(\d{2})/([^/?#]+?)-a(\d+)$")


def get(url):
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"  ! {url} -> {status}", flush=True)
        return ""
    return text


def month_urls(year, month):
    """Sitemap file names on nrc.nl are not zero padded: 2026-9.xml, 2026-10.xml."""
    return [f"{UA_HOST}/sitemap/{year}-{month}.xml"]


def candidate_sitemaps():
    """Month files covering the window, plus anything the index adds."""
    urls = []
    d = date.fromisoformat(START).replace(day=1)
    end = date.fromisoformat(END)
    while d <= end:
        urls += month_urls(d.year, d.month)
        d = (d + timedelta(days=32)).replace(day=1)
    idx = get(f"{UA_HOST}/sitemap/index.xml")
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx):
        if re.search(r"/sitemap/\d{4}-\d{1,2}\.xml$", loc) and loc not in urls:
            m = re.search(r"/sitemap/(\d{4})-(\d{1,2})\.xml$", loc)
            if m and START[:7] <= f"{m.group(1)}-{int(m.group(2)):02d}" <= END[:7]:
                urls.append(loc)
    return urls


def main():
    entries = []           # (url, date)
    seen = set()
    for sm in candidate_sitemaps():
        xml = get(sm)
        print(f"sitemap {sm}: {len(xml)} chars", flush=True)
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml):
            m = URL_RE.search(loc)
            if not m:
                continue
            d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if not (START <= d <= END):
                continue
            url = loc.split("?")[0]
            if url in seen:
                continue
            seen.add(url)
            entries.append((url, d, m.group(4)))

    # recurring slug = puzzle or cartoon (same slug every day/week)
    days_per_slug = defaultdict(set)
    for _u, d, slug in entries:
        days_per_slug[slug].add(d)

    rows = []
    for url, d, slug in entries:
        if len(days_per_slug[slug]) >= RECUR_DAYS:
            continue
        if slug in PUZZLE_SLUGS and len(slug.split("-")) <= 5:
            continue
        rows.append((url, d))

    rows.sort()
    with open(OUT, "w") as f:
        for url, d in rows:
            f.write(f"{url}\t{d}\n")

    per = defaultdict(int)
    for _u, d in rows:
        per[d] += 1
    for d in sorted(per):
        print(f"{d}\t{per[d]}")
    print(f"total {len(rows)} urls over {len(per)} days", flush=True)


if __name__ == "__main__":
    main()
