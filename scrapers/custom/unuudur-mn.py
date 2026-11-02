#!/usr/bin/env python3
import sys, re, os, json
from datetime import datetime

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

BASE = 'https://www.unuudur.mn'
CATEGORY = '/as/niitlel'  # news section (articles)
START = datetime.strptime('2026-09-25', '%Y-%m-%d')
END = datetime.strptime('2026-10-25', '%Y-%m-%d')

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'unuudur-mn.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
records = []
page = 1
while True:
    url = f"{BASE}{CATEGORY}?page={page}"
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed fetching page {page}: {status}')
        break
    # Find article blocks
    # pattern captures href and date
    # Pattern 1: anchors with explicit title class
    pattern1 = re.compile(r'<a[^>]+href="(?P<href>[^\"]+)"[^>]*class="[^\"]*(?:article-item__title|news-item__title)[^\"]*"[^>]*>.*?</a>.*?<div[^>]*class="[^\"]*(?:article-item__date|news-item__date)[^\"]*"[^>]*>.*?<span[^>]*>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</span>', re.DOTALL)
    # Pattern 2: generic article links (e.g., sidebar articles) where date appears later in a news-item__date div
    pattern2 = re.compile(r'<a[^>]+href="(?P<href>/a/[^\"]+)"[^>]*>.*?<div[^>]*class="[^\"]*news-item__date[^\"]*"[^>]*>.*?<span[^>]*>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</span>', re.DOTALL)
    # Find matches from both patterns
    matches1 = pattern1.finditer(text)
    matches2 = pattern2.finditer(text)
    any_new = False
    for m in list(matches1) + list(matches2):
        link = m.group('href')
        if not link.startswith('http'):
            link = BASE + link
        date_str = m.group('date')
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            continue
        if d < START or d > END:
            continue
        key = (link, date_str)
        if key not in seen:
            seen.add(key)
            records.append(key)
            any_new = True
    # Determine newest date on this page to decide stopping
    dates_on_page = [datetime.strptime(m.group('date'), '%Y-%m-%d') for m in list(matches1) + list(matches2)]
    if dates_on_page:
        newest = max(dates_on_page)
        if newest < START:
            # No newer articles beyond this page
            break
    else:
        # no articles found, stop
        break
    if not any_new:
        # no new records but still articles, continue to next page up to a limit
        pass
    page += 1
    if page > 1000:
        break

# Write TSV sorted by date then URL
records.sort(key=lambda x: (x[1], x[0]))
with open(out_path, 'w', encoding='utf-8') as f:
    for link, date_str in records:
        f.write(f"{link}\t{date_str}\n")
print(f'Wrote {len(records)} URLs to {out_path}')
