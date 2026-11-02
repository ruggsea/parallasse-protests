#!/usr/bin/env python3
"""Khaosod (khaosod.co.th) URL lister for 2026-09-25 .. 2026-10-25.

Route: permissive robots.txt -> WP REST /wp-json/wp/v2/posts, ordered by date
descending, walked with a `before=<oldest date seen>` cursor (the site ignores
the `page` param entirely, so classic pagination duplicates pages). Listed
date = date-part of the REST local 'date' field (Asia/Bangkok, site
gmt_offset=+7; equals the news-sitemap <news:publication_date> to the second).
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "khaosod-co-th.tsv"

WIN_START = "2026-09-25T00:00:00"
WIN_END = "2026-10-25T23:59:59"
BASE = "https://www.khaosod.co.th/wp-json/wp/v2/posts"

seen = {}
cursor = WIN_END
last_oldest = None
stalls = 0
for step in range(400):
    url = (f"{BASE}?per_page=100&orderby=date&order=desc&before={cursor}"
           f"&_fields=date,link")
    items = None
    for attempt in range(4):
        status, text, _ = fetch(url)
        if status == 200 and text:
            items = json.loads(text)
            break
        time.sleep(5 * (attempt + 1))
    if status != 200 or not items:
        raise SystemExit(f"REST failed at cursor {cursor}: status {status}")
    if not items:
        break
    for it in items:
        d = it["date"][:10]
        if WIN_START[:10] <= d <= WIN_END[:10]:
            seen.setdefault(it["link"], d)
    oldest = min(it["date"] for it in items)
    print(f"step {step}: {len(items)} items, oldest {oldest}, unique {len(seen)}", flush=True)
    if oldest < WIN_START:
        break
    if oldest == last_oldest:
        stalls += 1
        if stalls >= 2:
            print("no progress twice, stopping", flush=True)
            break
        time.sleep(12)  # CDN serves a stale cached body; wait it out and refetch
        continue
    stalls = 0
    last_oldest = oldest
    cursor = oldest
    time.sleep(7)  # site caches wp-json bodies for a few seconds

OUT.parent.mkdir(parents=True, exist_ok=True)
day_count = Counter()
with open(OUT, "w", encoding="utf-8") as f:
    for u, d in sorted(seen.items(), key=lambda kv: (kv[1], kv[0])):
        f.write(f"{u}\t{d}\n")
        day_count[d] += 1
print(f"WROTE {len(seen)} urls to {OUT}")
for d in sorted(day_count):
    print(d, day_count[d])
