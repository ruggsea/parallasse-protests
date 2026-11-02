import json, sys, os
from datetime import datetime, timedelta
import sys

# Ensure the polite_fetch module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://euronews.al/wp-json/wp/v2/posts'
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)  # inclusive
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'euronews-al.tsv'))

def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S')

def fetch_page(page):
    params = (
        f'after={iso(START)}',
        f'before={iso(END + timedelta(days=1))}',
        'per_page=100',
        f'page={page}',
        '_fields=date_gmt,link',
    )
    url = f"{BASE_URL}?{'&'.join(params)}"
    status, text, _ = fetch(url)
    if status != 200:
        # treat as end of pagination
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f'JSON error on page {page}: {e}', file=sys.stderr)
        return []

def main():
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    seen = {}
    per_day = {}
    page = 1
    while True:
        items = fetch_page(page)
        if not items:
            break
        for entry in items:
            # date_gmt like '2026-10-25T14:59:02'
            try:
                dt = datetime.strptime(entry['date_gmt'], '%Y-%m-%dT%H:%M:%S')
            except Exception:
                continue
            if not (START.date() <= dt.date() <= END.date()):
                continue
            url = entry['link']
            if url in seen:
                continue
            seen[url] = dt.date().isoformat()
            # store url

            day = dt.date().isoformat()
            per_day.setdefault(day, 0)
            per_day[day] += 1
        page += 1
    # write TSV
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for url in sorted(seen):
            date_part = seen[url]
            f.write(f"{url}\t{date_part}\n")
    # Print per‑day counts
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")

if __name__ == '__main__':
    main()
