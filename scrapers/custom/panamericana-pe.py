#!/usr/bin/env python3
import sys, json, os
from datetime import datetime, timedelta

# Add path for polite_fetch module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

BASE_URL = 'https://freenewsapi.ai/v1/search?host=www.panamericana.pe,panamericana.pe'
SIZE = 100  # max per request
START = datetime.strptime('2026-09-25', '%Y-%m-%d')
END = datetime.strptime('2026-10-25', '%Y-%m-%d')
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'panamericana-pe.tsv'))

os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)

seen = set()
results = []
offset = 0
while True:
    url = f"{BASE_URL}&size={SIZE}&offset={offset}&fields=title,url,published_at,lang"
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed request {url}: status {status}')
        sys.exit(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print('Invalid JSON')
        sys.exit(1)
    items = data.get('results') or []
    if not items:
        break
    for item in items:
        url = item.get('url')
        date_str = item.get('published_at') or item.get('date')
        if not url or not date_str:
            continue
        # date may include time and timezone, take first 10 chars
        date_part = date_str[:10]
        try:
            dt = datetime.strptime(date_part, '%Y-%m-%d')
        except ValueError:
            continue
        if dt < START:
            # since results are newest first, we can stop entire loop
            break
        if START <= dt <= END:
            if url not in seen:
                seen.add(url)
                results.append((url, date_part))
    else:
        # continue paging
        offset += SIZE
        continue
    # break outer while if inner break triggered (old date)
    break

# write TSV
with open(OUT_TSV, 'w', encoding='utf-8') as f:
    for u, d in results:
        f.write(f"{u}\t{d}\n")

# summary
print(f'Wrote {len(results)} URLs to {OUT_TSV}')
