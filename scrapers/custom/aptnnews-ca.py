#!/usr/bin/env python3
import sys, os, re, json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
BASE_URL = 'https://www.aptnnews.ca/feed/'

seen = set()
results = []
page = 1
max_pages = 500  # safety
while page <= max_pages:
    url = f"{BASE_URL}?paged={page}"
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Status {status} fetching {url}, stopping', file=sys.stderr)
        break
    # parse XML
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'XML parse error on page {page}: {e}', file=sys.stderr)
        break
    items = root.findall('.//item')
    if not items:
        break
    added_any = False
    for it in items:
        link_el = it.find('link')
        date_el = it.find('pubDate')
        if link_el is None or date_el is None:
            continue
        link = link_el.text.strip()
        if link in seen:
            continue
        # parse pubDate like 'Mon, 26 Oct 2026 23:38:42 +0000'
        try:
            dt = datetime.strptime(date_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
        except ValueError:
            continue
        # convert to naive UTC
        dt = dt.replace(tzinfo=None)
        if START <= dt <= END:
            seen.add(link)
            results.append((link, dt.date().isoformat()))
            added_any = True
        elif dt < START:
            # once we see a date older than start, we can stop after this page
            pass
    # if no new items in range and earliest date < start, break
    # Determine earliest date in this page
    dates = [datetime.strptime(it.find('pubDate').text.strip(), '%a, %d %b %Y %H:%M:%S %z').replace(tzinfo=None) for it in items if it.find('pubDate') is not None]
    if dates and min(dates) < START:
        break
    page += 1

# write output TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'aptnnews-ca.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, d in results:
        f.write(f"{url}\t{d}\n")

# Print summary per day
from collections import Counter
counter = Counter(d for _, d in results)
for day in sorted(counter):
    print(f'{day}: {counter[day]} URLs')
print('Total URLs:', len(results))

# Sample 4 URLs for verification
import random
sample = random.sample(results, min(4, len(results)))
for url, d in sample:
    s, txt, _ = fetch(url)
    if s == 200:
        print('Sample', url, 'len', len(txt))
    else:
        print('Sample fetch failed', url, 'status', s)
