#!/usr/bin/env python3

import sys
import xml.etree.ElementTree as ET
import os
from datetime import datetime, timedelta

# Ensure polite_fetch is available
sys.path.insert(0, "scrapers")
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch not found\n")
    sys.exit(1)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
SITEMAP_URL = "https://www.businesspost.ie/news-sitemap.xml"

status, text, _ = fetch(SITEMAP_URL)
if status != 200:
    sys.stderr.write(f"Failed to fetch sitemap: {status}\n")
    sys.exit(1)

# Parse XML with namespaces
ns = {"news": "http://www.google.com/schemas/sitemap-news/0.9"}
root = ET.fromstring(text)
entries = {}
for url_el in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
    loc_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    news_el = url_el.find("news:news", ns)
    if loc_el is None or news_el is None:
        continue
    pub_el = news_el.find("news:publication_date", ns)
    if pub_el is None:
        continue
    date_part = pub_el.text[:10]  # YYYY-MM-DD
    try:
        pub_date = datetime.strptime(date_part, "%Y-%m-%d").date()
    except Exception:
        continue
    if START.date() <= pub_date <= END.date():
        date_str = date_part
        url = loc_el.text.strip()
        entries[url] = date_str

# Write TSV
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
out_path = os.path.join(base_dir, "data", "urls_custom", "businesspost-ie.tsv")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    for url, date_str in sorted(entries.items()):
        f.write(f"{url}\t{date_str}\n")

# Print per‑day counts
counts = {}
for d in entries.values():
    counts[d] = counts.get(d, 0) + 1
for d in sorted(counts):
    print(f"{d}: {counts[d]} URLs")
