#!/usr/bin/env python3
"""MEGA TV (megatv.com, Greece) - article URLs for 2026-09-25 .. 2026-10-25.

Route: robots.txt (permissive) names https://www.megatv.com/sitemap.xml, which is a
sitemapindex from the arnebrachhold XML-Sitemap-Generator. Among its 971 entries are
per-month "post" urlsets:

    https://www.megatv.com/sitemap-pt-post-YYYY-MM.xml

Each urlset entry is just <loc>URL</loc> (no lastmod), but every article permalink is
WordPress-dated: https://www.megatv.com/YYYY/MM/DD/slug/ - the date part of the path is
the publication date the site itself states (it equals the page's JSON-LD datePublished
and the <time> element on every page we re-fetched). So two requests (2026-09, 2026-10)
cover the whole window; no recursion, no paging.

A few pages we measured are video/photo stubs whose extracted article body is a couple of
sentences (under ~1500 characters): they are listed in THIN below and left out, so the
TSV holds real articles.
"""
import collections
import os
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/megatv-com.tsv")
START, END = "2026-09-25", "2026-10-25"
MONTHS = ("2026-09", "2026-10")

# measured as video / photo stubs with under ~1500 chars of article body
THIN = {
    "ayta-einai-ta-xrysa-epaggelmata",
    "euroleague-o-olympiakos-perese-xeiropedes-stous-tourkous",
    "aek-simera-i-megali-maxi-me-tin-mantsester-siti-gia-to-champions-league",
    "aek-apopse-i-maxi-me-tin-mantsester-siti-gia-to-champions-league",
    "anavrasmos-sto-politiko-skiniko-me-fonto-tis-kinitopoiiseis-stin-eyropi",
    "aithrios-o-kairos-simera-triti-9",
    "alvania-ogdoi-imera-kinitopoiiseon-epeisodion-sta-tirana",
}
PATH_DATE = re.compile(r"megatv\.com/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)/?$")


def sitemap_urls():
    for m in MONTHS:
        url = f"https://www.megatv.com/sitemap-pt-post-{m}.xml"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"  {url}: status {status}", file=sys.stderr)
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text):
            yield loc


def main():
    rows = {}
    per_day = collections.Counter()
    for loc in sitemap_urls():
        mm = PATH_DATE.search(loc)
        if not mm:
            continue
        y, mo, d, slug = mm.groups()
        day = f"{y}-{mo}-{d}"
        if not (START <= day <= END):
            continue
        if slug in THIN:
            continue
        rows[loc] = day
        per_day[day] += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    items = sorted(rows.items())
    with open(OUT, "w", encoding="utf-8") as f:
        for url, day in items:
            f.write(f"{url}\t{day}\n")

    print(f"megatv-com: wrote {len(items)} URLs over {len(per_day)} days -> {OUT}")
    for day in sorted(per_day):
        print(f"  {day}\t{per_day[day]}")


if __name__ == "__main__":
    main()
