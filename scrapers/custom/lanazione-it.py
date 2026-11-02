#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAPS = [
    "https://www.lanazione.it/feedservice/sitemap/lan/articles/2026/week/sitemap.xml",
    "https://www.lanazione.it/feedservice/sitemap/lan/articles/2026/month/sitemap.xml",
]

urls_by_date = {}
all_urls = set()

for sitemap_url in SITEMAPS:
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        print(f"Failed to fetch {sitemap_url}: status {status}", file=sys.stderr)
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error for {sitemap_url}: {e}", file=sys.stderr)
        continue
    # namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        # extract date part
        try:
            dt = datetime.datetime.fromisoformat(lastmod.text.rstrip('Z'))
        except ValueError:
            # fallback split
            dt = datetime.datetime.strptime(lastmod.text[:10], "%Y-%m-%d")
        date = dt.date()
        if date < START or date > END:
            continue
        if url in all_urls:
            continue
        all_urls.add(url)
        urls_by_date.setdefault(date, []).append(url)

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'lanazione-it.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for date in sorted(urls_by_date):
        for u in urls_by_date[date]:
            f.write(f"{u}\t{date.isoformat()}\n")

# Print per‑day counts
for date in sorted(urls_by_date):
    print(f"{date}: {len(urls_by_date[date])} URLs")
