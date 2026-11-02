#!/usr/bin/env python3
"""Scrape taz.de article URLs for 2026-09-25 to 2026-10-25.

Uses the public XML sitemaps advertised in robots.txt:
  https://taz.de/sitemap-article-online-2026-09-01-2026-09-30.xml
  https://taz.de/sitemap-article-online-2026-10-01-2026-10-31.xml
The sitemaps contain <url><loc> and <lastmod> entries.  The
<lastmod> is taken as the publication date.

Output: data/urls_custom/taz-de.tsv with lines:
    URL<TAB>YYYY-MM-DD
No header, unique URLs.
"""

import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# make sure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(__file__, "..", "..", "..", "scrapers")))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAPS = [
    "https://taz.de/sitemap-article-online-2026-09-01-2026-09-30.xml",
    "https://taz.de/sitemap-article-online-2026-10-01-2026-10-31.xml",
]

out_path = os.path.abspath(os.path.join(__file__, "..", "..", "..", "data", "urls_custom", "taz-de.tsv"))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
per_day = defaultdict(int)

for sm_url in SITEMAPS:
    status, text, _ = fetch(sm_url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch sitemap {sm_url}: status {status}\n")
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        sys.stderr.write(f"XML parse error for {sm_url}: {e}\n")
        continue
    # namespaces may be present; ignore them by using .//url
    for url_el in root.findall('.//{*}url'):
        loc_el = url_el.find('{*}loc')
        lm_el = url_el.find('{*}lastmod')
        if loc_el is None or lm_el is None:
            continue
        url = loc_el.text.strip()
        lastmod_raw = lm_el.text.strip()
        # parse date portion
        try:
            dt = datetime.datetime.fromisoformat(lastmod_raw)
        except ValueError:
            # fallback: take first 10 chars
            dt = datetime.datetime.strptime(lastmod_raw[:10], "%Y-%m-%d")
        d = dt.date()
        if START <= d <= END:
            if url not in seen:
                seen.add(url)
                per_day[d] += 1

# write TSV
with open(out_path, "w", encoding="utf-8") as f:
    for url in sorted(seen):
        # retrieve the stored date from per_day dict; need date for each url – we lost mapping.
        # Re‑parse to map url->date (simple second pass).
        pass

# Second pass to output URL with its date (preserve order by date then URL)
url_date = {}
for sm_url in SITEMAPS:
    status, text, _ = fetch(sm_url)
    if status != 200:
        continue
    root = ET.fromstring(text)
    for url_el in root.findall('.//{*}url'):
        loc_el = url_el.find('{*}loc')
        lm_el = url_el.find('{*}lastmod')
        if loc_el is None or lm_el is None:
            continue
        url = loc_el.text.strip()
        if url not in seen:
            continue
        lastmod_raw = lm_el.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(lastmod_raw)
        except ValueError:
            dt = datetime.datetime.strptime(lastmod_raw[:10], "%Y-%m-%d")
        d = dt.date()
        if START <= d <= END:
            url_date[url] = d.isoformat()

with open(out_path, "w", encoding="utf-8") as f:
    for url in sorted(url_date):
        f.write(f"{url}\t{url_date[url]}\n")

# print per‑day counts
for day in sorted(per_day):
    print(f"{day}: {per_day[day]} URLs")
