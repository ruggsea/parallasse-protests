#!/usr/bin/env python3
"""List vesti.bg article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (200, permissive, names /sitemap.xml) -> /sitemap.xml index
-> per-category urlsets. Each <url> carries <lastmod>, which equals the
article page JSON-LD datePublished to the second (verified on 2 samples:
6271637 -> 2026-09-30T21:18:00+03:00, 6273599 -> 2026-10-20T20:52:00+03:00).
The /sitemap/latest_news urlset also carries news:publication_date, which is
used when present.

Union of: latest_news + category/{bulgaria,sviat,pari,razvlechenia,tehnologii}
+ galleries. razvlechenia is an empty urlset and vicove_all/* only reach back
to 2026-02, so they are skipped (checked 2026-10-26).
"""
import os
import re
import sys
import datetime
import xml.etree.ElementTree as ET

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

BASE = "https://www.vesti.bg"
SITEMAPS = [
    f"{BASE}/sitemap/latest_news",
    f"{BASE}/sitemap/category/bulgaria",
    f"{BASE}/sitemap/category/sviat",
    f"{BASE}/sitemap/category/pari",
    f"{BASE}/sitemap/category/razvlechenia",
    f"{BASE}/sitemap/category/tehnologii",
    f"{BASE}/sitemap/galleries",
]

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "news": "http://www.google.com/schemas/sitemap-news/0.9"}

# article URLs end in -<id>, e.g. .../bulgaria/some-slug-6271637
ARTICLE_RE = re.compile(r"^https?://(www\.)?vesti\.bg/[a-z0-9]+(?:/[a-z0-9-]+)*-?\d{5,}$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

OUTPUT_TSV = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "vesti-bg.tsv"))


def parse_iso_date(s):
    if not s:
        return None
    m = DATE_RE.match(s.strip())
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def main():
    found = {}  # url -> date (earliest wins on dup)
    for sm_url in SITEMAPS:
        status, text, _ = fetch(sm_url)
        if status != 200 or not text:
            print(f"skip {sm_url}: status {status}", file=sys.stderr)
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            print(f"skip {sm_url}: parse error {e}", file=sys.stderr)
            continue
        n = 0
        for url_el in root.findall("sm:url", NS):
            loc_el = url_el.find("sm:loc", NS)
            if loc_el is None or not loc_el.text:
                continue
            url = loc_el.text.strip()
            if not ARTICLE_RE.match(url):
                continue
            # prefer news:publication_date, fall back to lastmod
            d_el = url_el.find("news:news/news:publication_date", NS)
            d = parse_iso_date(d_el.text if d_el is not None and d_el.text else None)
            if d is None:
                lm_el = url_el.find("sm:lastmod", NS)
                d = parse_iso_date(lm_el.text if lm_el is not None and lm_el.text else None)
            if d is None or not (START <= d <= END):
                continue
            prev = found.get(url)
            if prev is None or d < prev:
                found[url] = d
            n += 1
        print(f"{sm_url}: {n} article urls in window (total known {len(found)})")

    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    per_day = {}
    for url, d in found.items():
        per_day.setdefault(d, []).append(url)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as out:
        for d in sorted(per_day):
            for u in sorted(per_day[d]):
                out.write(f"{u}\t{d.isoformat()}\n")
    total = 0
    for d in sorted(per_day):
        total += len(per_day[d])
        print(f"{d.isoformat()}: {len(per_day[d])} URLs")
    print(f"Wrote {total} URLs to {OUTPUT_TSV}")
    for key in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {key}: {len(per_day.get(datetime.date.fromisoformat(key), []))} urls")


if __name__ == "__main__":
    main()
