#!/usr/bin/env python3
"""List YTN (South Korea) article URLs published 2026-09-25..2026-10-25.

Route (verified): robots.txt is permissive (allow all) and lists a sitemap:
https://www.ytn.co.kr/sitemap/google_sitemap.xml which is a sitemap index
pointing to several sitemap files (e.g. sitemap0.xml, sitemap1.xml, ...).
Each sitemap file is a <urlset> containing <url> entries with
  <loc> – the article URL (mostly https://www.ytn.co.kr/_ln/…)
  <news:publication_date> – ISO timestamp of the publication date.
The publication date matches the date shown on the article page, so we use it.
We fetch each sitemap, extract URLs whose publication_date falls within the
window START..END, deduplicate, and write them to a TSV file with a tab‑separated
date (YYYY-MM-DD).
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START, END = "2026-09-25", "2026-10-25"
SITEMAP_INDEX = "https://www.ytn.co.kr/sitemap/google_sitemap.xml"
OUT = Path("data/urls_custom/ytn-co-kr.tsv")

# Regexes to capture <loc> and <news:publication_date> inside a <url> block.
LOC_RE = re.compile(r"<loc>\s*<!\[CDATA\[(https?://[^\]]+)\]\]>\s*</loc>")
DATE_RE = re.compile(r"<news:publication_date>\s*<!\[CDATA\[([^<]+)\]\]>\s*</news:publication_date>")
# Regex for sitemap index entries.
SITEMAP_RE = re.compile(r"<loc>\s*<!\[CDATA\[(https?://[^\]]+)\]\]>\s*</loc>")


def fetch_sitemap_urls(sitemap_url: str):
    status, text, _ = fetch(sitemap_url)
    if status != 200 or not text:
        print(f"WARN: failed to fetch {sitemap_url} status={status}", file=sys.stderr)
        return []
    entries = []
    # Split by <url> block to keep loc and date together.
    for block in re.split(r"<url>", text)[1:]:
        # each block ends with </url>
        loc_match = LOC_RE.search(block)
        date_match = DATE_RE.search(block)
        if loc_match and date_match:
            url = loc_match.group(1).strip()
            date_iso = date_match.group(1).strip()
            # convert ISO like 2026-10-26T15:58:00+09:00 to YYYY-MM-DD
            date = date_iso.split('T')[0]
            entries.append((url, date))
    return entries


def main():
    # Iterate over sequential sitemap files (sitemap0.xml, sitemap1.xml, ...) until a fetch fails or returns no URLs.
    seen = {}
    i = 0
    while True:
        sm_url = f"https://www.ytn.co.kr/sitemap/sitemap{i}.xml"
        urls = fetch_sitemap_urls(sm_url)
        if not urls:
            # Stop when a sitemap is missing or empty.
            break
        for url, date in urls:
            if START <= date <= END and url not in seen:
                seen[url] = date
        i += 1
        if i > 1000:
            print("WARN: exceeded 1000 sitemap files, stopping", file=sys.stderr)
            break

    if not seen:
        print("FAIL: no URLs found in window", file=sys.stderr)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(seen, key=lambda u: (seen[u], u)):
            f.write(f"{url}\t{seen[url]}\\n")

    counts = Counter(seen.values())
    print(f"wrote {len(seen)} unique URLs to {OUT}")
    for day in sorted(counts):
        print(f"  {day}: {counts[day]}")

    # sanity check per‑day minimums (>=15) for three sample dates
    for sample in ["2026-09-30", "2026-10-10", "2026-10-20"]:
        cnt = counts.get(sample, 0)
        if cnt < 15:
            print(f"WARNING: only {cnt} URLs for {sample}", file=sys.stderr)

if __name__ == "__main__":
    main()
