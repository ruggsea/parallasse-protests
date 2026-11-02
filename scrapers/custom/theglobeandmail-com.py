#!/usr/bin/env python3
import sys, os, csv
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET

# Add scrapers directory to path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://www.theglobeandmail.com/arc/outboundfeeds/news-sitemap/?outputType=xml"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/theglobeandmail-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
per_day = {}
offset = 0
while True:
    url = BASE_URL if offset == 0 else f"{BASE_URL}&from={offset}"
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"Fetch failed ({status}) for {url}", file=sys.stderr)
        break
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error: {e}", file=sys.stderr)
        break
    # namespaces
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    urls = root.findall('.//ns:url', ns)
    if not urls:
        break
    oldest_in_page = None
    for u in urls:
        loc_el = u.find('ns:loc', ns)
        pub_el = u.find('.//news:publication_date', ns)
        if loc_el is None or pub_el is None:
            continue
        loc = loc_el.text.strip()
        pub_str = pub_el.text.strip()
        try:
            pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
        except ValueError:
            continue
        pub_date = pub_dt.date()
        if oldest_in_page is None or pub_date < oldest_in_page:
            oldest_in_page = pub_date
        if START <= pub_date <= END:
            if loc not in seen:
                seen.add(loc)
                per_day.setdefault(pub_date, []).append(loc)
    # If the earliest date in this page is before START, we can stop fetching further older pages
    if oldest_in_page and oldest_in_page < START:
        break
    offset += len(urls)

# Write TSV
with open(out_path, 'w', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    for d in sorted(per_day):
        for u in per_day[d]:
            writer.writerow([u, d.isoformat()])

# Print counts per day
for d in sorted(per_day):
    print(f"{d.isoformat()}: {len(per_day[d])} URLs")
