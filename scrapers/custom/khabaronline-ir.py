#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Add path for polite_fetch
sys.path.insert(0, "scrapers")
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("Error: polite_fetch not found\n")
    raise

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

# Persian months for our window: Mehr (07) and Aban (08)
months = {"07": (4, 30),  # start day 4 (2026-09-25 corresponds to 1405/07/04)
          "08": (1, 2)}  # up to day 2 for Oct 25

base_url = "https://www.khabaronline.ir/sitemap/1405"

results = {}

for month, (day_start, day_end) in months.items():
    for day in range(day_start, day_end + 1):
        day_str = f"{day:02d}"
        sitemap_url = f"{base_url}/{month}/{day_str}/sitemap.xml"
        status, text, _ = fetch(sitemap_url)
        if status != 200:
            # skip missing sitemaps
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            continue
        for url_elem in root.findall('.//url'):
            loc = url_elem.findtext('loc')
            lastmode = url_elem.findtext('lastmode')
            if not loc or not lastmode:
                continue
            # extract date part from timestamp
            try:
                pub_date = datetime.datetime.fromisoformat(lastmode.rstrip('Z')).date()
            except Exception:
                continue
            if START <= pub_date <= END:
                results[loc] = pub_date.isoformat()

# Write TSV
out_path = os.path.join('data', 'urls_custom', 'khabaronline-ir.tsv')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, date in sorted(results.items()):
        f.write(f"{url}\t{date}\n")

# Print per-day counts
counts = {}
for d in results.values():
    counts[d] = counts.get(d, 0) + 1
for d in sorted(counts):
    print(f"{d}\t{counts[d]}")
