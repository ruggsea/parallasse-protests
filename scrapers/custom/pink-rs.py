#!/usr/bin/env python3
import sys, os, xml.etree.ElementTree as ET, datetime

# Add path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://pink.rs/rss-feed'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/pink-rs.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
counts = {}

page = 1
while True:
    url = f'{BASE_URL}?page={page}' if page > 1 else BASE_URL
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: {status}', file=sys.stderr)
        break
    root = ET.fromstring(text)
    entries = root.findall('{http://www.w3.org/2005/Atom}entry')
    if not entries:
        break
    stop = False
    for ent in entries:
        link_el = ent.find('{http://www.w3.org/2005/Atom}link')
        if link_el is None:
            continue
        article_url = link_el.get('href')
        updated_el = ent.find('{http://www.w3.org/2005/Atom}updated')
        if updated_el is None:
            continue
        dt = datetime.datetime.fromisoformat(updated_el.text.rstrip('Z'))
        date = dt.date()
        if date < START:
            stop = True
            break
        if START <= date <= END:
            if article_url not in seen:
                seen.add(article_url)
                counts.setdefault(date, 0)
                counts[date] += 1
                with open(out_path, 'a', encoding='utf-8') as f:
                    f.write(f"{article_url}\t{date.isoformat()}\n")
    if stop:
        break
    page += 1

# Print summary
for d in sorted(counts):
    print(f'{d}: {counts[d]} URLs')
