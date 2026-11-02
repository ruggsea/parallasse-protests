#!/usr/bin/env python3
import sys, os, datetime, time, json
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# The repository adds /scrapers to sys.path in other scripts; adjust accordingly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://www.radio24.ilsole24ore.com'
SITEMAP_URL = f'{BASE_URL}/sitemap.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'radio24-ilsole24ore-com.tsv'))

os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)


def parse_date(s):
    try:
        return datetime.datetime.strptime(s[:10], '%Y-%m-%d').date()
    except Exception:
        return None

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None

def collect_urls_from_sitemap(root):
    urls = []
    # sitemapindex or urlset
    if root.tag.endswith('sitemapindex'):
        for sm in root.findall('.//{*}sitemap'):
            loc = sm.find('{*}loc')
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    elif root.tag.endswith('urlset'):
        for url in root.findall('.//{*}url'):
            loc = url.find('{*}loc')
            lm = url.find('{*}lastmod')
            if loc is not None and loc.text:
                urls.append((loc.text.strip(), lm.text.strip() if lm is not None else None))
    return urls

# Use Wayback CDX as primary source (sitemap not available)
entries = []
cdx_url = (
    f'http://web.archive.org/cdx/search/cdx?url=radio24.ilsole24ore.com/*'
    f'&from={START.isoformat().replace("-", "")}'
    f'&to={END.isoformat().replace("-", "")}'
    f'&output=json&collapse=urlkey'
)
status, text, _ = fetch(cdx_url)
if status == 200:
    try:
        data = json.loads(text)
        fields = data[0]
        url_idx = fields.index('url') if 'url' in fields else 1
        timestamp_idx = fields.index('timestamp') if 'timestamp' in fields else 0
        for row in data[1:]:
            url = row[url_idx]
            ts = row[timestamp_idx]
            d = datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
            if START <= d <= END:
                entries.append((url, d.isoformat()))
    except Exception:
        pass

# Deduplicate while preserving first date seen
unique = {}
for u, d in entries:
    if u not in unique:
        unique[u] = d

# Write TSV
with open(OUT_TSV, 'w', encoding='utf-8') as f:
    for u, d in sorted(unique.items()):
        f.write(f"{u}\t{d}\n")

# Print per‑day counts
from collections import Counter
cnt = Counter(d for d in unique.values())
for day in sorted(cnt):
    print(f"{day}: {cnt[day]} URLs")

print(f"Total URLs written: {len(unique)}")
