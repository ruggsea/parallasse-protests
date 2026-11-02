#!/usr/bin/env python3
"""Scrape article URLs from Semana.com for a given date window.
Uses the public news sitemap (allowed by robots.txt) via polite_fetch.
Writes TSV with URL and publication date (YYYY-MM-DD).
"""
import os, sys, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable (project adds scrapers to sys.path)
import urllib.request
import time

def fetch(url, retries=3, delay=1):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SemanaScraper/1.0)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.getcode()
                text = resp.read().decode('utf-8', errors='ignore')
                headers = dict(resp.getheaders())
                return status, text, headers
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            else:
                return 0, '', {}


START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://www.semana.com/arc/outboundfeeds/news-sitemap/?outputType=xml"

seen = set()
results = []
day_counts = {}

offset = 0
while True:
    url = BASE if offset == 0 else f"{BASE}&from={offset}"
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch {url}: status {status}", file=sys.stderr)
        break
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error at {url}: {e}", file=sys.stderr)
        break
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    urls = root.findall('.//s:url', ns)
    if not urls:
        break
    page_oldest = None
    for u in urls:
        loc_el = u.find('s:loc', ns)
        if loc_el is None or not loc_el.text:
            continue
        link = loc_el.text.strip()
        pub_el = u.find('.//news:publication_date', ns)
        if pub_el is None or not pub_el.text:
            continue
        pub_dt = pub_el.text.strip()[:10]
        try:
            pub_date = datetime.datetime.strptime(pub_dt, "%Y-%m-%d").date()
        except ValueError:
            continue
        if page_oldest is None or pub_date < page_oldest:
            page_oldest = pub_date
        if pub_date < START:
            continue
        if pub_date > END:
            continue
        if link in seen:
            continue
        seen.add(link)
        results.append((link, pub_dt))
        day_counts.setdefault(pub_dt, 0)
        day_counts[pub_dt] += 1
    if page_oldest is not None and page_oldest < START:
        break
    offset += 100

# Write TSV
out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'semana-com.tsv')
with open(out_path, 'w', encoding='utf-8') as f:
    for link, date in results:
        f.write(f"{link}\t{date}\n")

# Print per‑day counts
for d in sorted(day_counts):
    print(f"{d}\t{day_counts[d]}")
