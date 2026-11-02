#!/usr/bin/env python3
import sys, os, csv, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
import re
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'organiser-org.tsv'))
os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def date_in_range(d: datetime.date) -> bool:
    return START <= d <= END

sitemap_url = 'https://organiser.org/lotus-news-sitemap.xml'
status, text, _ = fetch(sitemap_url)
if status != 200:
    print(f'Failed to fetch sitemap {sitemap_url}: {status}', file=sys.stderr)
    sys.exit(1)

root = ET.fromstring(text)
ns = {
    's': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}
counts = {}
rows = []
# First, parse the news sitemap (lotus-news-sitemap.xml) for recent entries with explicit publication_date.
for url_el in root.findall('s:url', ns):
    loc_el = url_el.find('s:loc', ns)
    news_el = url_el.find('news:news', ns)
    if loc_el is None or news_el is None:
        continue
    pub_date_el = news_el.find('news:publication_date', ns)
    if pub_date_el is None:
        continue
    pub_iso = pub_date_el.text.strip()
    try:
        pub_dt = datetime.datetime.fromisoformat(pub_iso)
    except ValueError:
        continue
    pub_date = pub_dt.date()
    if not date_in_range(pub_date):
        continue
    url = loc_el.text.strip()
    rows.append((url, pub_date.isoformat()))
    counts[pub_date] = counts.get(pub_date, 0) + 1

# --- Additional source: regular post sitemaps ---
index_url = 'https://organiser.org/sitemap_index.xml'
status, index_text, _ = fetch(index_url)
if status == 200:
    try:
        idx_root = ET.fromstring(index_text)
    except ET.ParseError:
        idx_root = None
    if idx_root is not None:
        idx_ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for sm in idx_root.findall('s:sitemap', idx_ns):
            loc_el = sm.find('s:loc', idx_ns)
            mod_el = sm.find('s:lastmod', idx_ns)
            if loc_el is None:
                continue
            sm_url = loc_el.text.strip()
            # heuristic: skip if sitemap lastmod older than start date
            if mod_el is not None:
                try:
                    mod_date = datetime.datetime.fromisoformat(mod_el.text.strip().split('T')[0]).date()
                except Exception:
                    mod_date = None
                if mod_date and mod_date < START:
                    continue
            s_status, s_text, _ = fetch(sm_url)
            if s_status != 200:
                continue
            try:
                s_root = ET.fromstring(s_text)
            except ET.ParseError:
                continue
            for u_el in s_root.findall('s:url', idx_ns):
                loc = u_el.find('s:loc', idx_ns)
                if loc is None:
                    continue
                url = loc.text.strip()
                m = re.search(r'/([12][0-9]{3})/(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/', url)
                if not m:
                    continue
                y, mo, d = m.group(1), m.group(2), m.group(3)
                try:
                    pub_date = datetime.date(int(y), int(mo), int(d))
                except ValueError:
                    continue
                if not date_in_range(pub_date):
                    continue
                rows.append((url, pub_date.isoformat()))
                counts[pub_date] = counts.get(pub_date, 0) + 1
else:
    print(f'Failed to fetch sitemap index {index_url}: {status}', file=sys.stderr)

# Deduplicate URLs
unique = {}
for url, date_str in rows:
    if url not in unique:
        unique[url] = date_str

with open(OUT_TSV, 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    for url, date_str in unique.items():
        writer.writerow([url, date_str])

# Print per‑day counts
for day in sorted(counts):
    print(f'{day}\t{counts[day]}')

print(f'Wrote {len(unique)} unique URLs to {OUT_TSV}')
