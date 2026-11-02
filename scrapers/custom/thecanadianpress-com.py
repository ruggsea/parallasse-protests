import re
import sys
from datetime import datetime, timedelta
import os

# Ensure the fetch utility is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thecanadianpress-com.tsv'))
os.makedirs(os.path.dirname(output_path), exist_ok=True)

seen = set()
per_day_counts = {}

cur = START
while cur <= END:
    date_str = cur.strftime('%Y/%m/%d')
    archive_url = f'https://www.thecanadianpress.com/archive/{date_str}/'
    status, text, _ = fetch(archive_url)
    if status != 200:
        # skip if archive page unavailable
        cur += timedelta(days=1)
        continue
    # Find all hrefs to the domain
    urls = re.findall(r'href=["\'](https?://www\.thecanadianpress\.com/[^"\']+)["\']', text, re.IGNORECASE)
    # Keep only URLs that contain the date component (simple heuristic)
    filtered = [u for u in urls if f'/{date_str}/' in u]
    new_urls = []
    for u in filtered:
        if u not in seen:
            seen.add(u)
            new_urls.append(u)
    per_day_counts[date_str] = len(new_urls)
    # Write incrementally to avoid keeping everything in memory
    with open(output_path, 'a', encoding='utf-8') as f:
        for u in new_urls:
            f.write(f"{u}\t{cur.strftime('%Y-%m-%d')}\n")
    cur += timedelta(days=1)

# Summary
print('Finished. URLs written per day:')
for d, cnt in sorted(per_day_counts.items()):
    print(f'{d}: {cnt}')
