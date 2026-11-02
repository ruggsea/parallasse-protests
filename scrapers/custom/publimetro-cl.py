#!/usr/bin/env python3
import os, sys, csv, datetime, xml.etree.ElementTree as ET
# Add project root to sys.path for polite_fetch
scrapers_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, scrapers_dir)
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

repo_root = os.path.abspath(os.path.join(scrapers_dir, '..'))
out_path = os.path.abspath(os.path.join(repo_root, 'data', 'urls_custom', 'publimetro-cl.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
per_day_counts = {}

current = START
while current <= END:
    date_str = current.isoformat()
    sitemap_url = f"https://www.publimetro.cl/arc/outboundfeeds/sitemap/{date_str}/?outputType=xml"
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        # No sitemap for this date
        current += datetime.timedelta(days=1)
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        current += datetime.timedelta(days=1)
        continue
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    count = 0
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        if url in seen:
            continue
        if lastmod_el is not None and lastmod_el.text:
            pub_date = lastmod_el.text.strip().split('T')[0]
        else:
            parts = url.split('/')
            try:
                y, m, d = parts[4], parts[5], parts[6]
                pub_date = f"{y}-{m}-{d}"
            except Exception:
                pub_date = date_str
        seen.add(url)
        with open(out_path, 'a', encoding='utf-8') as f:
            f.write(f"{url}\t{pub_date}\n")
        count += 1
    # If not enough URLs, fallback to Wayback CDX for this date
    if count < 15:
        cdx_url = f"http://web.archive.org/cdx/search/cdx?url=publimetro.cl/*&from={date_str.replace('-', '')}&to={date_str.replace('-', '')}&output=json&collapse=urlkey"
        status_cdx, text_cdx, _ = fetch(cdx_url)
        if status_cdx == 200:
            try:
                import json as _json
                rows = _json.loads(text_cdx)
                # first row is header
                for row in rows[1:]:
                    if len(row) < 3:
                        continue
                    orig_url = row[2]
                    if orig_url in seen:
                        continue
                    seen.add(orig_url)
                    with open(out_path, 'a', encoding='utf-8') as f:
                        f.write(f"{orig_url}\t{date_str}\n")
                    count += 1
                    if count >= 15:
                        break
            except Exception:
                pass
    per_day_counts[date_str] = count
    current += datetime.timedelta(days=1)

# Print per‑day counts
for d, c in sorted(per_day_counts.items()):
    print(f"{d}\t{c}")
