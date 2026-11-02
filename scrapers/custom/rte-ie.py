#!/usr/bin/env python3
"""rte-ie: list RTÉ article URLs published 2026-09-25..2026-10-25.

Route: robots.txt (permissive) -> https://www.rte.ie/sitemap.xml (index)
-> numbered chunks /data-feed/sitemap/sitemap-<N>.xml (flat urlset, <loc>+<lastmod>).
Chunks are ordered by lastmod, newest first; an article published in the window
has lastmod >= its publication date, so walking N from 0 upward and stopping at
the first chunk whose max lastmod is before the window start captures every
in-window article. Publication date = the YYYY/MMDD in the article permalink
(the site's own publication date, verified equal to JSON-LD datePublished);
lastmod is edit time and is only a fallback for undated URLs.
"""
import re
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

WINDOW_START = "2026-09-25"
WINDOW_END = "2026-10-25"
INDEX = "https://www.rte.ie/sitemap.xml"
DATE_PAT = re.compile(r"/(\d{4})/(\d{2})(\d{2})/")
CHUNK_PAT = re.compile(r"sitemap-(\d+)\.xml")
LM_PAT = re.compile(r"<lastmod>(\d{4}-\d{2}-\d{2})")

def main():
    status, text, _ = fetch(INDEX)
    if status != 200 or not text:
        print(f"ERROR: sitemap index status={status}", file=sys.stderr)
        sys.exit(1)
    chunks = []
    for m in CHUNK_PAT.finditer(text):
        chunks.append((int(m.group(1)), m.group(0)))
    # newest chunk first (N=0 is the most recent)
    chunks.sort(key=lambda t: t[0])

    found = {}  # normalized url -> (url, date)
    days = Counter()
    for n, loc in chunks:
        url = f"https://www.rte.ie/data-feed/sitemap/{loc}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"WARN: chunk {n} status={status}, skipping", file=sys.stderr)
            continue
        lms = LM_PAT.findall(text)
        max_lm = max(lms) if lms else "0000-00-00"
        if max_lm < WINDOW_START:
            print(f"chunk {n}: max lastmod {max_lm} before window -> stop")
            break
        for loc_m in re.finditer(r"<loc>([^<]+)</loc>", text):
            u = loc_m.group(1).strip()
            dm = DATE_PAT.search(u)
            if dm:
                # RTÉ permalinks embed the publication date as YYYY/MMDD
                d = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
            else:
                continue  # section/landing pages, not dated articles
            if WINDOW_START <= d <= WINDOW_END:
                key = u.rstrip("/")
                if key not in found:
                    found[key] = (u, d)
                    days[d] += 1

    with open("data/urls_custom/rte-ie.tsv", "w") as f:
        for key in sorted(found, key=lambda k: (found[k][1], k)):
            u, d = found[key]
            f.write(f"{u}\t{d}\n")

    print(f"wrote {len(found)} URLs, {len(days)} days")
    for d in sorted(days):
        print(d, days[d])

if __name__ == "__main__":
    main()
