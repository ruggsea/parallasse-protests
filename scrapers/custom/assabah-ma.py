#!/usr/bin/env python3
import sys, json, time
from datetime import datetime, timedelta

# Ensure polite_fetch is on sys.path
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE_URL = "https://assabah.ma"
API_ENDPOINT = f"{BASE_URL}/wp-json/wp/v2/posts"
# Date window
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25, 23, 59, 59)

per_page = 100
page = 1
results = []
while True:
    url = (
        f"{API_ENDPOINT}?after={START.isoformat()}&before={END.isoformat()}"
        f"&per_page={per_page}&_fields=link,date&page={page}"
    )
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch page {page}, status {status}", file=sys.stderr)
        break
    try:
        posts = json.loads(text)
    except Exception as e:
        print(f"JSON decode error on page {page}: {e}", file=sys.stderr)
        break
    if not posts:
        break
    for p in posts:
        link = p.get("link")
        date_str = p.get("date")  # ISO8601
        try:
            dt = datetime.fromisoformat(date_str)
            date_key = dt.strftime("%Y-%m-%d")
        except Exception:
            date_key = date_str[:10]
        results.append((link, date_key))
    print(f"Fetched {len(posts)} posts from page {page}")
    page += 1
    time.sleep(1)  # be polite

# Deduplicate while preserving order
seen = set()
unique = []
for link, d in results:
    if link not in seen:
        seen.add(link)
        unique.append((link, d))

out_path = "data/urls_custom/assabah-ma.tsv"
with open(out_path, "w", encoding="utf-8") as f:
    for link, d in unique:
        f.write(f"{link}\t{d}\n")

# Print per‑day counts for quick verification
from collections import Counter
cnt = Counter(d for _, d in unique)
for day in sorted(cnt):
    print(f"{day}: {cnt[day]} URLs")
print(f"Total URLs written: {len(unique)}")
