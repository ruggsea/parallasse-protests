#!/usr/bin/env python3
"""Radio-Canada (ici.radio-canada.ca) article URL list, 2026-09-25..2026-10-25.

Route: robots.txt permits crawling and lists a news sitemap at
https://ici.radio-canada.ca/info/sitemaps.xml. The sitemap is a single
<urlset> where each <url> contains <loc> (article URL) and <lastmod>
(timestamp). The date part of <lastmod> matches the publication date
(the site’s JSON‑LD datePublished has been verified against several
samples). We therefore emit each article URL together with the date
YYYY‑MM‑DD extracted from <lastmod>.
"""

import datetime as dt
import re
import sys
import time

# Ensure our helper module is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
SITEMAP = "https://ici.radio-canada.ca/info/sitemaps.xml"
OUT = "data/urls_custom/ici-radio-canada-ca.tsv"

LOC_RE = re.compile(r"<loc>(.*?)</loc>")
LM_RE = re.compile(r"<lastmod>(.*?)</lastmod>")

def fetch_sitemap(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        status, text, _ = fetch(url, cache=False)
        if status == 200 and text:
            return text
        # polite back‑off
        time.sleep(5 * (attempt + 1))
    print(f"WARN: failed to fetch sitemap after {retries} attempts (status {status})", file=sys.stderr)
    return None

def main():
    text = fetch_sitemap(SITEMAP)
    if not text:
        sys.exit(1)
    locs = LOC_RE.findall(text)
    lms = LM_RE.findall(text)
    found: dict[str, str] = {}
    by_day: dict[str, int] = {}
    for i, url in enumerate(locs):
        # safety: ensure we have a matching lastmod entry
        date_str = None
        if i < len(lms):
            # keep only date part
            date_str = lms[i][:10]
        if not date_str:
            continue
        try:
            d = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (START <= d <= END):
            continue
        if url not in found:
            found[url] = date_str
            by_day[date_str] = by_day.get(date_str, 0) + 1
    # write TSV
    with open(OUT, "w", encoding="utf-8") as fp:
        for url in sorted(found):
            fp.write(f"{url}\t{found[url]}\n")
    total = len(found)
    print(f"TOTAL {total} unique urls")
    cur = START
    while cur <= END:
        print(f"  {cur.isoformat()}: {by_day.get(cur.isoformat(), 0)}")
        cur += dt.timedelta(days=1)

if __name__ == "__main__":
    main()
