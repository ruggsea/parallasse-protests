#!/usr/bin/env python3
import sys, os, csv, time
from datetime import datetime, date, timezone
from email.utils import parsedate_to_datetime

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found')

BASE_FEED = 'https://www.naftemporiki.gr/feed/'
START_DATE = date(2026, 9, 25)
END_DATE = date(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'naftemporiki-gr.tsv'))

def fetch_page(page):
    url = f"{BASE_FEED}?paged={page}"
    status, text, _ = fetch(url)
    return status, text

def parse_items(xml_text):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall('.//item'):
        link_el = item.find('link')
        date_el = item.find('pubDate')
        if link_el is None or date_el is None:
            continue
        link = link_el.text.strip()
        pub_str = date_el.text.strip()
        try:
            dt = parsedate_to_datetime(pub_str)
            # Normalize to UTC date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            pub_date = dt.date()
        except Exception:
            continue
        items.append((link, pub_date))
    return items

def main():
    seen = {}
    page = 1
    consecutive_no_new = 0
    while True:
        status, txt = fetch_page(page)
        if status != 200:
            print(f"Failed to fetch page {page}, status {status}")
            break
        items = parse_items(txt)
        if not items:
            print(f"No items on page {page}, stopping.")
            break
        added_this_page = 0
        for link, pub_date in items:
            if pub_date < START_DATE or pub_date > END_DATE:
                continue
            if link not in seen:
                seen[link] = pub_date
                added_this_page += 1
        if added_this_page == 0:
            consecutive_no_new += 1
        else:
            consecutive_no_new = 0
        # Stop if we have several pages with no new URLs (likely past window)
        if consecutive_no_new >= 5:
            break
        page += 1
        time.sleep(0.5)  # polite pause
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for link, pub_date in sorted(seen.items(), key=lambda x: (x[1], x[0])):
            writer.writerow([link, pub_date.isoformat()])
    # Print per-day counts
    from collections import Counter
    cnt = Counter(seen.values())
    for d in sorted(cnt):
        print(f"{d}: {cnt[d]} URLs")
    print(f"Total URLs: {len(seen)}")

if __name__ == '__main__':
    main()
