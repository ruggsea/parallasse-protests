#!/usr/bin/env python3
"""klix.ba (Bosnia and Herzegovina): article URLs published 2026-09-25..2026-10-25.

Route: https://www.klix.ba/sitemap.xml (declared in robots.txt, robots 200) lists
https://www.klix.ba/sitemap/vijesti/N -- the recent-articles sitemaps, paginated,
newest first, ~40000 <url><loc>...<lastmod>... entries per page. Page 1 alone
spans 2026-03-25..2026-10-25, so the whole window is inside pages 1-3; we fetch
up to 3 pages and keep every entry whose sitemap lastmod date falls in the window.
Each entry is a real article URL (https://www.klix.ba/<section>/.../<9-digit id>);
non-article URLs are dropped by the id pattern. Dates are the sitemap lastmod
dates, i.e. as the site states them.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/klix-ba.tsv"
WIN_LO, WIN_HI = "2026-09-25", "2026-10-25"
ENTRY = re.compile(
    r"<loc>\s*(https://www\.klix\.ba/\S+?)\s*</loc>\s*<changefreq>\w+</changefreq>\s*<lastmod>\s*(\d{4}-\d{2}-\d{2})"
)
ARTICLE = re.compile(r"/\d{9}$")


def main():
    found = {}  # url -> lastmod date (first occurrence wins)
    for page in (1, 2, 3):
        url = f"https://www.klix.ba/sitemap/vijesti/{page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"sitemap page {page}: HTTP {status}, stopping", file=sys.stderr)
            break
        entries = ENTRY.findall(text)
        for u, d in entries:
            if WIN_LO <= d <= WIN_HI and ARTICLE.search(u) and u not in found:
                found[u] = d
        oldest_in_page = entries[-1][1][:10] if entries else "?"
        print(f"page {page}: {len(entries)} entries, oldest lastmod {oldest_in_page}, window so far {len(found)}")
        if oldest_in_page < WIN_LO:
            break  # window fully covered

    if not found:
        print("no in-window entries found", file=sys.stderr)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    per = defaultdict(int)
    with OUT.open("w") as f:
        for u, d in sorted(found.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{u}\t{d}\n")
            per[d] += 1
    for d in sorted(per):
        print(f"{d}\t{per[d]}")
    print(f"wrote {len(found)} URLs over {len(per)} days -> {OUT}")


if __name__ == "__main__":
    main()
