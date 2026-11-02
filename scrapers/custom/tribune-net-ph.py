#!/usr/bin/env python3
"""Daily Tribune (Philippines), tribune.net.ph — list article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
- robots.txt is permissive (Allow: /; only /api/ /upload/ /media/ disallowed; Sitemap lines:
  sitemap.xml, news-sitemap.xml, image-sitemap.xml).
- news-sitemap.xml is a flat urlset but only ~55 entries (~3 days back) — insufficient.
- sitemap.xml is a template artifact (thejournal.ie content) — useless.
- No WP REST (404). Site is Next.js.
- /latest?page=N is server-rendered and paginates the full site feed in publish order,
  ~18 articles/page. Article permalinks carry the publication date in the path
  (/YYYY/MM/DD/slug) and the article page displays that same date in Manila local time
  ("20 October 2026" for /2026-10-20/..., datePublished 2026-10-20T08:55:22.529Z UTC =
  16:55 PHT, same local date). So the URL-path date IS the site-stated date.
- Paginate /latest until the newest article on a page predates 2026-09-25.

Output: data/urls_custom/tribune-net-ph.tsv — "URL<TAB>YYYY-MM-DD", unique, no header.
"""
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://tribune.net.ph"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
ROOT = Path(".")
OUT = ROOT / "data/urls_custom/tribune-net-ph.tsv"

ART = re.compile(r'href="(/(20\d{2})/(\d{2})/(\d{2})/[^"#?]+)"')


def main():
    found = {}  # url -> date
    stop_after = None
    page = 1
    while page <= 500:
        url = f"{BASE}/latest?page={page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"page {page}: status {status}, stopping", file=sys.stderr)
            break
        items = []
        for path, y, mo, d in ART.findall(text):
            try:
                dt = date(int(y), int(mo), int(d))
            except ValueError:
                continue
            items.append((dt, BASE + path))
        if not items:
            print(f"page {page}: no articles, stopping", file=sys.stderr)
            break
        new = 0
        for dt, aurl in items:
            if aurl not in found:
                found[aurl] = dt
                new += 1
        newest = max(dt for dt, _ in items)
        oldest = min(dt for dt, _ in items)
        print(f"page {page}: {len(items)} links ({new} new), {oldest} .. {newest}", file=sys.stderr)
        if newest < START:
            break
        page += 1

    rows = []
    for aurl, dt in sorted(found.items(), key=lambda kv: (kv[1], kv[0])):
        if START <= dt <= END:
            rows.append((aurl, dt.isoformat()))
    # unique URLs (first date wins; dict already deduped, but be explicit)
    seen = set()
    out_rows = []
    for aurl, d in rows:
        if aurl in seen:
            continue
        seen.add(aurl)
        out_rows.append((aurl, d))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for aurl, d in out_rows:
            f.write(f"{aurl}\t{d}\n")

    per_day = Counter(d for _, d in out_rows)
    print(f"wrote {len(out_rows)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    missing = [d.isoformat() for d in [date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)]
               if per_day.get(d.isoformat(), 0) < 15]
    if missing:
        print(f"WARNING: thin days (<15): {missing}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
