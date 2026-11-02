#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + datetime.timedelta(days=n)

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'farsnews-ir.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

seen = set()
records = []

for day in daterange(START, END):
    sitemap_url = f"https://farsnews.ir/sitemaps/contents/{day.year:04d}/{day.month:02d}/{day.day:02d}/index001.xml"
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        # Skip missing sitemap
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        continue
    # namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        lm_text = lastmod.text.strip()
        try:
            lm_dt = datetime.datetime.fromisoformat(lm_text.replace('Z', '+00:00'))
        except Exception:
            continue
        lm_date = lm_dt.date()
        if lm_date < START or lm_date > END:
            continue
        if url in seen:
            continue
        seen.add(url)
        records.append((url, lm_date.isoformat()))
    # end for each url
# end for each day

# Write TSV
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date_str in records:
        f.write(f"{url}\t{date_str}\n")

# Print per‑day counts
from collections import Counter
cnt = Counter(date for _, date in records)
for day in sorted(cnt):
    print(f"{day}\t{cnt[day]}")
