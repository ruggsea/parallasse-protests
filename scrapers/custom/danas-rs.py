#!/usr/bin/env python3
"""Scrape article URLs from Danas (danas.rs) via the RSS feed.
Collect URLs published between 2026-09-25 and 2026-10-25 inclusive.
Writes TSV to data/urls_custom/danas-rs.tsv with columns: URL<TAB>YYYY-MM-DD.
Duplicates are removed.
"""
import sys
import os
import datetime
import xml.etree.ElementTree as ET

def main():
    # add path for polite_fetch
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from polite_fetch import fetch

    start = datetime.date(2026, 9, 25)
    end = datetime.date(2026, 10, 25)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'danas-rs.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    seen = set()
    # feed pagination – keep fetching pages until we encounter an item older than start
    page = 1
    while True:
        url = f'https://www.danas.rs/feed/?paged={page}'
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f'Failed to fetch page {page}, status {status}', file=sys.stderr)
            break
        root = ET.fromstring(text)
        items = root.findall('.//item')
        if not items:
            break
        reached_older = False
        for item in items:
            link_el = item.find('link')
            date_el = item.find('pubDate')
            if link_el is None or date_el is None:
                continue
            link = link_el.text.strip()
            # parse pubDate, e.g., "Mon, 26 Oct 2026 06:36:20 +0000"
            try:
                dt = datetime.datetime.strptime(date_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
            except Exception:
                continue
            pub_date = dt.date()
            if pub_date < start:
                reached_older = True
                continue
            if pub_date > end:
                # future items, skip
                continue
            if link not in seen:
                seen.add((link, pub_date))
        if reached_older:
            break
        page += 1
        # safety guard to avoid endless loop
        if page > 1000:
            break

    # write TSV sorted by date then URL
    with open(out_path, 'w', encoding='utf-8') as f:
        for link, pub_date in sorted(seen, key=lambda x: (x[1], x[0])):
            f.write(f"{link}\t{pub_date.isoformat()}\n")
    # report counts per day
    from collections import Counter
    cnt = Counter([d.isoformat() for _, d in seen])
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
