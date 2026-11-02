#!/usr/bin/env python3
"""Scraper for El Colombiano (elcolombiano.com)
Collects article URLs published between 2026-09-25 and 2026-10-25 (inclusive)
using the Google News sitemap (sitemapforgoogle.xml). Writes a TSV file with
URL<TAB>YYYY-MM-DD to data/urls_custom/elcolombiano-com.tsv.
"""
import sys
import os
from datetime import date
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable (project root → scrapers folder)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
# Also add the scrapers directory itself
scrapers_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if scrapers_dir not in sys.path:
    sys.path.insert(0, scrapers_dir)

try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch module not found\n')
    sys.exit(1)

START = date(2026, 9, 25)
END = date(2026, 10, 25)

SITEMAP_URL = 'https://www.elcolombiano.com/sitemapforgoogle.xml'

status, text, _ = fetch(SITEMAP_URL)
if status != 200:
    sys.stderr.write(f'Failed to fetch sitemap: HTTP {status}\n')
    sys.exit(1)

# Parse the sitemap XML using regex (handles namespaces without parsing)
import re
entries = []
for loc, pub_dt in re.findall(r'<loc>(.*?)</loc>.*?<news:publication_date>(.*?)</news:publication_date>', text, re.DOTALL):
    url = loc.strip()
    try:
        pub_date = date.fromisoformat(pub_dt.split('T')[0])
    except Exception:
        continue
    if START <= pub_date <= END:
        entries.append((url, pub_date.isoformat()))
# Deduplicate URLs
seen = set()
unique_entries = []
for url, d in entries:
    if url not in seen:
        seen.add(url)
        unique_entries.append((url, d))

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'elcolombiano-com.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, d in unique_entries:
        f.write(f"{url}\t{d}\n")

# Print simple per‑day stats
from collections import Counter
counter = Counter(d for _, d in unique_entries)
for day in sorted(counter):
    print(f"{day}\t{counter[day]}")
