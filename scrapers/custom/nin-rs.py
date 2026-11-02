#!/usr/bin/env python3
import sys, os
import datetime
import xml.etree.ElementTree as ET

# Insert path for polite_fetch
sys.path.insert(0, "scrapers")
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch not found\n")
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
SITEMAP = "https://www.nin.rs/sitemap/news.xml"

status, text, _ = fetch(SITEMAP)
if status != 200:
    sys.stderr.write(f"Failed to fetch sitemap: {status}\n")
    sys.exit(1)

# Parse XML
root = ET.fromstring(text)
ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
# Some sitemaps omit namespace; handle both
if root.tag.startswith('{'):
    # namespace present
    ns_tag = root.tag.split('}')[0].strip('{')
    ns = {'ns': ns_tag}
    url_elems = root.findall('ns:url', ns)
else:
    url_elems = root.findall('url')

entries = []
seen = set()
for url_el in url_elems:
    loc_el = url_el.find('ns:loc', ns) if 'ns' in ns else url_el.find('loc')
    lastmod_el = url_el.find('ns:lastmod', ns) if 'ns' in ns else url_el.find('lastmod')
    if loc_el is None or lastmod_el is None:
        continue
    url = loc_el.text.strip()
    lastmod_text = lastmod_el.text.strip()
    # parse date part
    try:
        dt = datetime.datetime.fromisoformat(lastmod_text)
    except ValueError:
        # fallback split
        dt = datetime.datetime.strptime(lastmod_text[:10], "%Y-%m-%d")
    date = dt.date()
    if START <= date <= END:
        if url not in seen:
            seen.add(url)
            entries.append((url, date.isoformat()))

# Sort by date then url
entries.sort(key=lambda x: (x[1], x[0]))

out_dir = os.path.join(os.getcwd(), "data", "urls_custom")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "nin-rs.tsv")
with open(out_path, "w", encoding="utf-8") as f:
    for url, date_str in entries:
        f.write(f"{url}\t{date_str}\n")

# Print per‑day counts
from collections import Counter
cnt = Counter(date for _, date in entries)
for d in sorted(cnt):
    print(f"{d}: {cnt[d]}")

print(f"Wrote {len(entries)} URLs to {out_path}")
