#!/usr/bin/env python3
import sys, os, csv, datetime, json

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.exit('polite_fetch not found')

FEED_URL = 'https://www.tagesschau.de/infoservices/startseite-sitemap-102~rss2.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

status, text, _ = fetch(FEED_URL)
if status != 200:
    sys.exit(f'Failed to fetch feed, status {status}')

import xml.etree.ElementTree as ET
root = ET.fromstring(text)
items = root.findall('.//item')

urls_by_date = {}
for it in items:
    link_el = it.find('link')
    if link_el is None or not link_el.text:
        continue
    url = link_el.text.strip()
    # Try dc:date first
    dc_date_el = it.find('{http://purl.org/dc/elements/1.1/}date')
    if dc_date_el is not None and dc_date_el.text:
        date_str = dc_date_el.text.strip()[:10]
    else:
        # fallback to pubDate e.g. 'Tue, 27 Oct 2026 05:20:26 +0100'
        pub_el = it.find('pubDate')
        if pub_el is None or not pub_el.text:
            continue
        try:
            dt = datetime.datetime.strptime(pub_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
            date_str = dt.date().isoformat()
        except Exception:
            continue
    try:
        d = datetime.date.fromisoformat(date_str)
    except Exception:
        continue
    if START <= d <= END:
        urls_by_date.setdefault(d, set()).add(url)

# Write output TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/tagesschau-de.tsv'))
json_out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../grids/custom/out/tagesschau-de.json.part'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    for day in sorted(urls_by_date):
        for u in sorted(urls_by_date[day]):
            writer.writerow([u, day.isoformat()])

# Determine low volume
required_days = [datetime.date(2026,9,30), datetime.date(2026,10,10), datetime.date(2026,10,20)]
low_volume = any(len(urls_by_date.get(d, [])) < 15 for d in required_days)
notes = {
    "day_counts": {d.isoformat(): len(urls_by_date.get(d, [])) for d in required_days},
    "total_urls": sum(len(s) for s in urls_by_date.values()),
    "low_volume": low_volume
}
with open(json_out_path, 'w', encoding='utf-8') as jf:
    json.dump({"script": "scrapers/custom/tagesschau-de.py", "notes": notes}, jf, ensure_ascii=False, indent=2)


