import os
import sys
import json
import time

# Ensure the scraper package is on sys.path
scraper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, scraper_dir)

from polite_fetch import fetch

# Output TSV path
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'sunnewsonline-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Date range for the query (inclusive)
START = "2026-09-25T00:00:00"
END = "2026-10-25T23:59:59"
PER_PAGE = 100

seen = set()
counts = {}
total = 0
page = 1

while True:
    api_url = (
        f"https://thesun.ng/wp-json/wp/v2/posts?after={START}&before={END}"
        f"&per_page={PER_PAGE}&page={page}"
    )
    status, text, _ = fetch(api_url)
    if status != 200:
        print(f"[ERROR] HTTP {status} for {api_url}", file=sys.stderr)
        break
    try:
        posts = json.loads(text)
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON on page {page}", file=sys.stderr)
        break
    if not posts:
        break
    for post in posts:
        link = post.get("link")
        date = post.get("date", "")[:10]
        if not link or not date:
            continue
        # Convert the thsun.ng domain to sunnewsonline.com as required
        sun_url = link.replace("thesun.ng", "sunnewsonline.com")
        if sun_url in seen:
            continue
        seen.add(sun_url)
        counts[date] = counts.get(date, 0) + 1
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(f"{sun_url}\t{date}\n")
        total += 1
    page += 1
    # Respect polite_fetch rate‑limiting (roughly 1 req/s)
    time.sleep(1)

print(f"Wrote {total} URLs to {out_path}")
for d in sorted(counts):
    print(f"{d}: {counts[d]}")
