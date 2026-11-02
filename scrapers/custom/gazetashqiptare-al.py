#!/usr/bin/env python3
"""gazetashqiptare.al (Albania) — WP REST post listing.
Route: permissive robots.txt (disallows only pagination/search) -> /wp-json/wp/v2/posts
with after/before window and per_page=100. Listed date = date part of REST 'date'
(site-local time; matches the /YYYY/MM/DD/ in the article URL and the page JSON-LD
datePublished). Writes data/urls_custom/gazetashqiptare-al.tsv.
"""
import sys, os, json, re
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from polite_fetch import fetch

BASE = "https://gazetashqiptare.al"
START = "2026-09-24T00:00:00"  # 1 day local margin before window start
END = "2026-10-26T23:59:59"    # 1 day local margin after window end
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"
PER_PAGE = 100

DATE_IN_URL = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")

collected = {}
page = 1
max_pages = 60  # safety cap
while page <= max_pages:
    url = (f"{BASE}/wp-json/wp/v2/posts?per_page={PER_PAGE}"
           f"&after={START}&before={END}&page={page}&_fields=date,link")
    status, text, _ = fetch(url)
    if status != 200:
        print(f"page {page}: HTTP {status}, stopping")
        break
    try:
        items = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"page {page}: bad JSON ({e}), stopping")
        break
    if not items:
        break
    for it in items:
        link = it.get("link") or ""
        dt = it.get("date") or ""
        if not link or not dt:
            continue
        link = link.replace("\\/", "/")
        # prefer the date in the site's own URL path (their stated publication day)
        m = DATE_IN_URL.search(link)
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else dt.split("T")[0]
        if not (WIN_START <= date <= WIN_END):
            continue
        if link not in collected:
            collected[link] = date
    print(f"page {page}: {len(items)} items, total {len(collected)}")
    if len(items) < PER_PAGE:
        break
    page += 1

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                        "data", "urls_custom", "gazetashqiptare-al.tsv"))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    for link, date in sorted(collected.items(), key=lambda x: (x[1], x[0])):
        f.write(f"{link}\t{date}\n")

counts = defaultdict(int)
for d in collected.values():
    counts[d] += 1
for d in sorted(counts):
    print(f"{d}\t{counts[d]}")
print(f"WROTE {len(collected)} URLs to {out_path}")
