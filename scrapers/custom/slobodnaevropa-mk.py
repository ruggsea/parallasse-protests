#!/usr/bin/env python3
import sys, os, gzip, io, datetime, xml.etree.ElementTree as ET
# Add the scrapers directory to sys.path for polite_fetch
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scrapers'))
sys.path.insert(0, base_dir)
try:
    from polite_fetch import fetch
except ImportError:
    print('Failed to import polite_fetch', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAPS = [
    'https://northmacedonia.rferl.org/sitemap_24_news.xml.gz',
    'https://northmacedonia.rferl.org/sitemap_24_latest.xml.gz',
]

results = []  # list of (url, date_str)
seen = set()

for sm_url in SITEMAPS:
    status, body, _ = fetch(sm_url)
    if status != 200:
        print(f'Failed to fetch {sm_url}: {status}', file=sys.stderr)
        continue
    # body may be bytes; ensure we have bytes
    if isinstance(body, str):
        data = body.encode('utf-8')
    else:
        data = body
    try:
        xml_bytes = gzip.decompress(data)
    except Exception:
        # not gzipped, use as is
        xml_bytes = data
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f'XML parse error for {sm_url}: {e}', file=sys.stderr)
        continue
    ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for url_el in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        # Try publication_date from news namespace
        pub_date = None
        news_el = url_el.find('news:news', ns)
        if news_el is not None:
            pub_el = news_el.find('news:publication_date', ns)
            if pub_el is not None and pub_el.text:
                pub_date = pub_el.text.strip()
        # fallback to lastmod
        if not pub_date:
            lm_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            if lm_el is not None and lm_el.text:
                pub_date = lm_el.text.strip()
        if not pub_date:
            continue
        try:
            dt = datetime.datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        except Exception:
            continue
        d = dt.date()
        if START <= d <= END:
            if url not in seen:
                seen.add(url)
                results.append((url, d.isoformat()))

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'slobodnaevropa-mk.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date_str in sorted(results, key=lambda x: (x[1], x[0])):
        f.write(f"{url}\t{date_str}\n")

# Print per‑day counts
from collections import Counter
cnt = Counter([date for _, date in results])
for day in sorted(cnt):
    print(f'{day}: {cnt[day]} URLs')
print('Total URLs:', len(results))
