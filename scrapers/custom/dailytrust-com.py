#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET

# Add scraper directory to path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date(dt_str: str) -> datetime.date:
    # dt_str like 2026-09-28T18:59:22+00:00
    return datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()

results = {}
# start from a high index where recent entries appear, walk upwards until dates older than START
sitemap_idx = 560
started = False
while True:
    url = f'https://dailytrust.com/post-sitemap{sitemap_idx}.xml'
    status, txt, _ = fetch(url)
    if status != 200:
        break
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        break
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = root.findall('sm:url', ns)
    if not urls:
        break
    # Newest entry date
    first_node = urls[0]
    first_lm = first_node.find('sm:lastmod', ns)
    if first_lm is None:
        break
    first_date = parse_date(first_lm.text)
    if first_date < START:
        # If we have already started collecting, we are past the window.
        if started:
            break
        else:
            sitemap_idx += 1
            continue
    else:
        started = True
    for node in urls:
        loc_el = node.find('sm:loc', ns)
        lastmod_el = node.find('sm:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        pub_date = parse_date(lastmod_el.text)
        if START <= pub_date <= END:
            results[loc_el.text] = pub_date.isoformat()
    sitemap_idx += 1

# Write TSV
out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'dailytrust-com.tsv')
with open(out_path, 'w', encoding='utf-8') as f:
    for loc, date_str in sorted(results.items()):
        f.write(f"{loc}\t{date_str}\n")
print(f"Wrote {len(results)} URLs to {out_path}")
