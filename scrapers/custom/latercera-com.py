#!/usr/bin/env python3
import sys, os, xml.etree.ElementTree as ET, datetime, collections

# Add polite_fetch path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'latercera-com.tsv'))
os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)

seen = set()
per_day = collections.Counter()
# also keep mapping loc -> date
loc_date = {}

# Sitemap base URL
BASE = 'https://www.latercera.com/arc/outboundfeeds/news-sitemap/'
# pagination via ?outputType=xml&from=N (N increments by 200) – continue until dates older than START.
offset = 0
step = 200
while True:
    url = f"{BASE}?outputType=xml&from={offset}" if offset else f"{BASE}?outputType=xml"
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed fetch {url}: {status}', file=sys.stderr)
        break
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'XML parse error at {url}: {e}', file=sys.stderr)
        break
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    urls = root.findall('ns:url', ns)
    if not urls:
        break
    # track if any entry falls into range
    batch_has_in_range = False
    batch_oldest = None
    for u in urls:
        loc_el = u.find('ns:loc', ns)
        news_date_el = u.find('.//news:publication_date', ns)
        if loc_el is None or news_date_el is None:
            continue
        loc = loc_el.text.strip()
        pub_str = news_date_el.text.strip()
        try:
            pub_dt = datetime.datetime.fromisoformat(pub_str.rstrip('Z'))
        except ValueError:
            continue
        pub_date = pub_dt.date()
        # keep oldest date seen in this batch
        if batch_oldest is None or pub_date < batch_oldest:
            batch_oldest = pub_date
        if START <= pub_date <= END:
            batch_has_in_range = True
            if loc not in seen:
                seen.add(loc)
                per_day[pub_date] += 1
                loc_date[loc] = pub_date
    # If the oldest date of this batch is before START we can stop fetching further pages.
    if batch_oldest is not None and batch_oldest < START:
        break
    # otherwise advance offset
    offset += step

# Write TSV (sorted by date then URL)
with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
    for loc in sorted(seen, key=lambda u: (loc_date[u], u)):
        f.write(f"{loc}\t{loc_date[loc].isoformat()}\n")

# Print per‑day counts for the window
print('URL counts per day:')
for day in (START + datetime.timedelta(days=i) for i in range((END - START).days + 1)):
    cnt = per_day.get(day, 0)
    if cnt:
        print(f"{day.isoformat()}: {cnt}")
