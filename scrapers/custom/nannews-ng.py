#!/usr/bin/env python3
"""nannews-ng (News Agency of Nigeria) — article URLs 2026-09-25 .. 2026-10-25.

Route: permissive robots.txt -> WP REST API /wp-json/wp/v2/posts with
after/before date filter, paginated. The REST 'date' field (site-local,
no offset) equals the page JSON-LD datePublished (+00:00) exactly, so it
is the date the site states for each article.
"""
import json
import os
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.nannews.ng/wp-json/wp/v2/posts"
AFTER = "2026-09-25T00:00:00"
BEFORE = "2026-10-25T23:59:59"
OUT = "data/urls_custom/nannews-ng.tsv"

urls = {}  # url -> date
page = 1
while True:
    url = (f"{BASE}?per_page=100&_fields=date,link"
           f"&after={AFTER}&before={BEFORE}&page={page}")
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"stop at page {page}: status {status}")
        break
    items = json.loads(text)
    if not isinstance(items, list) or not items:
        break
    for it in items:
        d = it.get("date", "")[:10]
        link = it.get("link", "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        if not ("2026-09-25" <= d <= "2026-10-25"):
            continue
        if link and link not in urls:
            urls[link] = d
    if len(items) < 100:
        break
    page += 1

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    for link in sorted(urls):
        f.write(f"{link}\t{urls[link]}\n")

counts = {}
for d in urls.values():
    counts[d] = counts.get(d, 0) + 1
for d in sorted(counts):
    print(d, counts[d])
print("total unique:", len(urls))
