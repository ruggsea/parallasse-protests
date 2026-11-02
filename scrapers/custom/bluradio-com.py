import os, sys, xml.etree.ElementTree as ET, datetime

# Add scraper utils path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise RuntimeError('polite_fetch not found; ensure scrapers/ is on PYTHONPATH')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URLS = [
    'https://www.bluradio.com/sitemap-202609.xml',
    'https://www.bluradio.com/sitemap-202610.xml',
]

results = {}
for sitemap_url in SITEMAP_URLS:
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        print(f'Failed to fetch {sitemap_url}: {status}')
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'XML parse error for {sitemap_url}: {e}')
        continue
    # namespaces handling – sitemap uses default namespace
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_elem in root.findall('.//ns:url', ns):
        loc = url_elem.find('ns:loc', ns)
        lastmod = url_elem.find('ns:lastmod', ns)
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        date_str = lastmod.text.strip()[:10]  # YYYY-MM-DD
        try:
            pub_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if START <= pub_date <= END:
            results[url] = date_str

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'bluradio-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date in sorted(results.items()):
        f.write(f"{url}\t{date}\n")

# Print per‑day counts
counts = {}
for date in results.values():
    counts[date] = counts.get(date, 0) + 1
for date in sorted(counts):
    print(f"{date}\t{counts[date]}")
