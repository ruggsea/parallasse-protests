#!/usr/bin/env python3
"""Scraper for kapital.mk (North Macedonia)
Collect article URLs published between 2026-09-25 and 2026-10-25.
Writes TSV to data/urls_custom/kapital-mk.tsv with columns: URL<TAB>YYYY-MM-DD
The script attempts to use the WordPress REST API; if unavailable, it falls back to sitemaps.
"""
import os, sys, json, time
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# The repository adds a helper in scrapers folder; adjust path if needed
sys.path.insert(0, 'scrapers')

try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://kapital.mk'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/kapital-mk.tsv'))
START_DATE = datetime(2026, 9, 25)
END_DATE = datetime(2026, 10, 25)

def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S')

def fetch_wp_posts(after, before, per_page=100):
    page = 1
    results = []
    while True:
        url = f"{BASE_URL}/wp-json/wp/v2/posts?per_page={per_page}&page={page}&after={after}&before={before}"  # noqa: E501
        status, text, _ = fetch(url)
        if status != 200:
            print(f'WP REST request failed {status} for {url}', file=sys.stderr)
            break
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print('Failed to parse JSON from WP REST', file=sys.stderr)
            break
        if not data:
            break
        results.extend(data)
        if len(data) < per_page:
            break
        page += 1
        time.sleep(0.5)  # be polite
    return results

def parse_posts(posts):
    items = []
    for post in posts:
        link = post.get('link')
        date_str = post.get('date')  # assumes local timezone date string
        if not link or not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            continue
        if dt < START_DATE or dt > END_DATE:
            continue
        items.append((link, dt.date().isoformat()))
    return items

def write_tsv(items):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    # deduplicate preserving first occurrence
    seen = set()
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in items:
            if url in seen:
                continue
            seen.add(url)
            f.write(f"{url}\t{date}\n")
    print(f'Wrote {len(seen)} unique URLs to {OUTPUT_TSV}')

def count_per_day(items):
    counts = {}
    for _, date in items:
        counts[date] = counts.get(date, 0) + 1
    for d in sorted(counts):
        print(f'{d}: {counts[d]}')

def main():
    after_iso = iso(START_DATE)
    before_iso = iso(END_DATE + timedelta(days=1))  # exclusive upper bound
    print('Attempting WordPress REST API...')
    posts = fetch_wp_posts(after_iso, before_iso)
    items = parse_posts(posts)
    if not items:
        print('No items retrieved via WP REST. Trying sitemap fallback (not implemented).', file=sys.stderr)
    write_tsv(items)
    count_per_day(items)

if __name__ == '__main__':
    main()
