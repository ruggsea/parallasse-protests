import sys, os, csv
import datetime
import xml.etree.ElementTree as ET

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scrapers')))
# Assuming polite_fetch module is at project root/scrapers (as per instruction)
# It provides fetch(url) returning (status, text, info)
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch import failed', file=sys.stderr)
    sys.exit(1)

BASE_URLS = [
    'https://radiomitre.cienradios.com/arc/outboundfeeds/sitemap/?outputType=xml',
    'https://radiomitre.cienradios.com/arc/outboundfeeds/news-sitemap/?outputType=xml'
]
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

unique = {}
step = 100
for BASE_URL in BASE_URLS:
    offset = 0
    while True:
        url = f'{BASE_URL}&from={offset}' if offset else BASE_URL
        status, text, _ = fetch(url)
        if status != 200:
            break
        if not text.strip():
            break
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            break
        urls_in_page = 0
        for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            lastmod_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            if loc_el is None or lastmod_el is None:
                continue
            url_str = loc_el.text.strip()
            lastmod_str = lastmod_el.text.strip()
            try:
                dt = datetime.datetime.fromisoformat(lastmod_str.rstrip('Z'))
            except ValueError:
                continue
            date = dt.date()
            if date < START_DATE:
                continue
            if START_DATE <= date <= END_DATE:
                if url_str not in unique:
                    unique[url_str] = date
                urls_in_page += 1
        if urls_in_page == 0:
            break
        offset += step

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'radiomitre-cienradios-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    for url, date in sorted(unique.items(), key=lambda kv: kv[1]):
        writer.writerow([url, date.isoformat()])

# Print per‑day counts
counts = {}
for d in unique.values():
    counts[d] = counts.get(d, 0) + 1
for d in sorted(counts):
    print(f'{d.isoformat()}: {counts[d]}')
