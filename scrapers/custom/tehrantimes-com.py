#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + datetime.timedelta(days=n)

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'tehrantimes-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
per_day_counts = {}

for day in daterange(START, END):
    url = f'https://www.tehrantimes.com/sitemap/{day.year}/{day.month:02d}/{day.day:02d}/sitemap.xml'
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: status {status}', file=sys.stderr)
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'XML parse error for {url}: {e}', file=sys.stderr)
        continue
    day_count = 0
    for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        lastmod_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
        if loc_el is None:
            continue
        link = loc_el.text.strip()
        if link in seen:
            continue
        seen.add(link)
        # date from lastmod if present, else use day
        date_str = day.isoformat()
        if lastmod_el is not None and lastmod_el.text:
            date_str = lastmod_el.text.strip()[:10]
        with open(out_path, 'a', encoding='utf-8') as f:
            f.write(f"{link}\t{date_str}\n")
        day_count += 1
    per_day_counts[day.isoformat()] = day_count
    print(f"{day.isoformat()}: {day_count} URLs")

print(f"Total unique URLs: {len(seen)}")
