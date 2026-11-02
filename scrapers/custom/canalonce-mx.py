#!/usr/bin/env python3
"""Canal Once (Mexico) news scraper.

Canal Once's news articles are published on oncenoticias.digital (its
"Once Noticias" news site; canalonce.mx itself is a JS shell whose own
sitemap dates stop at 2021 and contains no dated article URLs). The site is
plain WordPress with a permissive robots.txt (only /wp-admin/ disallowed),
so the route is the WP REST API:
  /wp-json/wp/v2/posts?_fields=date,link&after=...&before=...&page=N
(newest-first). The listed date is the article's datePublished as the page
states it in JSON-LD: the REST 'date' is local Mexico City time (fixed
UTC-6 since 2022), so listed date = local date + 6h, i.e. the UTC date.
Verified on sample 592886: REST 2026-10-25T21:34:32 local == page
datePublished 2026-10-26T03:34:32+00:00, so listed date matches the page
exactly. The Yoast post-sitemap lastmod is edit time and was not used.
"""
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://oncenoticias.digital"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
ROOT = Path(".")
OUT = ROOT / "data/urls_custom/canalonce-mx.tsv"

# WP date filters use the local post_date column; pass a 1-day margin on
# each side and filter by the (UTC) date part afterwards.
after = (START - timedelta(days=1)).isoformat() + "T00:00:00"
before = (END + timedelta(days=1)).isoformat() + "T23:59:59"

urls = {}  # url -> listed date (UTC, == page datePublished date)
page = 1
while page < 30:
    u = (f"{BASE}/wp-json/wp/v2/posts?per_page=100&_fields=date,link"
         f"&after={after}&before={before}&page={page}")
    st, t, _ = fetch(u)
    if st != 200 or not t:
        print(f"REST page {page}: status {st}, stopping", file=sys.stderr)
        break
    try:
        items = json.loads(t)
    except ValueError:
        print(f"REST page {page}: bad json, stopping", file=sys.stderr)
        break
    if not items:
        break
    for it in items:
        raw = it.get("date") or ""
        link = (it.get("link") or "").strip()
        if not link or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", raw):
            continue
        day = (datetime.fromisoformat(raw) + timedelta(hours=6)).date()
        if START <= day <= END and link not in urls:
            urls[link] = day.isoformat()
    print(f"page {page}: {len(items)} items, total {len(urls)}")
    if len(items) < 100:
        break
    page += 1

OUT.parent.mkdir(parents=True, exist_ok=True)
lines = sorted(urls.items(), key=lambda kv: (kv[1], kv[0]))
with open(OUT, "w", encoding="utf-8") as f:
    for link, d in lines:
        f.write(f"{link}\t{d}\n")

per_day = {}
for d in urls.values():
    per_day[d] = per_day.get(d, 0) + 1
print(f"WROTE {len(lines)} URLs to {OUT}")
for d in sorted(per_day):
    print(d, per_day[d])
for need in ("2026-09-30", "2026-10-10", "2026-10-20"):
    print(f"CHECK {need}: {per_day.get(need, 0)}")
