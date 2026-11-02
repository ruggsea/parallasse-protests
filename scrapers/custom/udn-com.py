#!/usr/bin/env python3
"""List UDN (udn.com) article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
  robots.txt (200, permissive for /news/* and sitemaps) names
  https://udn.com/sitemapxml/news/mapindex.xml, a sitemap index of weekly
  files  <section>T<YYYYMM>W<week>.xml  for sections 2 (news) and 1015 (opinion).
  Each <url> block contains the article <loc> and, after <priority>, an XML
  comment '<!-- YYYY-MM-DD HH:MM:SS -->' which is the PUBLICATION time
  (Taipei, +08:00): it matches the article page JSON-LD datePublished to the
  second (verified on /news/story/7327/9827414: comment 2026-10-20 23:58:02
  == datePublished 2026-10-20T23:58:02+08:00). <lastmod> is sitemap
  generation time and is only a fallback.

Weekly files W3/W4 of Oct and W4/W5 of Sep fully cover the window with ~600-1200
URLs/day in section 2 alone; we fetch W3..W5 Sep and W1..W4 Oct for both
sections (15 requests total), filter by the comment date, dedupe, and write
data/urls_custom/udn-com.tsv as URL<TAB>YYYY-MM-DD.
"""
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(REPO, "data", "urls_custom", "udn-com.tsv")
START, END = "2026-09-25", "2026-10-25"

WEEKLY = [
    # (section, month, week)
    ("2", "202609", "W3"), ("2", "202609", "W4"), ("2", "202609", "W5"),
    ("2", "202610", "W1"), ("2", "202610", "W2"), ("2", "202610", "W3"),
    ("2", "202610", "W4"),
    ("1015", "202609", "W3"), ("1015", "202609", "W4"), ("1015", "202609", "W5"),
    ("1015", "202610", "W1"), ("1015", "202610", "W2"), ("1015", "202610", "W3"),
    ("1015", "202610", "W4"),
]

URL_RE = re.compile(r"<url>(.*?)</url>", re.S)
LOC_RE = re.compile(r"<loc>(.*?)</loc>", re.S)
COMMENT_RE = re.compile(r"<!--\s*(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s*-->")
LASTMOD_RE = re.compile(r"<lastmod>(\d{4}-\d{2}-\d{2})")


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
            if status == 200 and text:
                return text
            print(f"  status {status} for {url} (attempt {i + 1})")
        except Exception as e:
            print(f"  error {e!r} for {url} (attempt {i + 1})")
        time.sleep(5 * (i + 1))
    return None


def main():
    found = {}  # url -> date (first occurrence wins)
    for section, month, week in WEEKLY:
        url = f"https://udn.com/sitemapxml/news/{section}T{month}{week}.xml"
        text = get(url)
        if text is None:
            print(f"SKIPPED {url}: no content after retries")
            continue
        n = 0
        for block in URL_RE.findall(text):
            loc = LOC_RE.search(block)
            if not loc:
                continue
            u = loc.group(1).strip()
            c = COMMENT_RE.search(block)
            d = c.group(1) if c else None
            if d is None:
                lm = LASTMOD_RE.search(block)
                d = lm.group(1) if lm else None
            if d is None or not (START <= d <= END):
                continue
            if u not in found:
                found[u] = d
                n += 1
        print(f"{url}: +{n} urls (total {len(found)})")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for u in sorted(found, key=lambda x: (found[x], x)):
            f.write(f"{u}\t{found[u]}\n")

    per_day = Counter(found.values())
    print(f"wrote {len(found)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    # sanity: all three check days
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {d}: {per_day.get(d, 0)}")


if __name__ == "__main__":
    main()
