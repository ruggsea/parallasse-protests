#!/usr/bin/env python3
"""Scrape Suara Merdeka article URLs for a date range.
Writes TSV with URL and publication date (YYYY-MM-DD).
Uses the news sitemap which contains <news:publication_date> and falls back to daily archive pages.
Respects robots.txt via polite_fetch.
"""
import sys, os, datetime, re, xml.etree.ElementTree as ET

# ensure polite_fetch importable (relative to repo root)
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

# Date range (inclusive)
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

# Output TSV path (relative to repo root)
out_path = "data/urls_custom/suaramerdeka-com.tsv"
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Track seen URLs to avoid duplicates
seen = set()
counts = {}

# Fetch the news sitemap (contains <news:publication_date>)
sitemap_url = "https://www.suaramerdeka.com/sitemap-news.xml"
status, text, _ = fetch(sitemap_url)
if status != 200:
    print(f"[ERROR] Failed to fetch sitemap {sitemap_url}: status {status}", file=sys.stderr)
    sys.exit(1)

ns = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}
root = ET.fromstring(text)
added = 0
for url_el in root.findall('ns:url', ns):
    loc_el = url_el.find('ns:loc', ns)
    if loc_el is None or not loc_el.text:
        continue
    url = loc_el.text.strip()
    pub_el = url_el.find('news:news/news:publication_date', ns)
    if pub_el is None or not pub_el.text:
        continue
    pub_date = pub_el.text.split('T')[0]
    try:
        pub_dt = datetime.datetime.fromisoformat(pub_date)
    except ValueError:
        continue
    pub_day = pub_dt.date()
    if not (START <= pub_day <= END):
        continue
    key = (url, pub_day.isoformat())
    if key in seen:
        continue
    seen.add(key)
    counts.setdefault(pub_day, 0)
    counts[pub_day] += 1
    with open(out_path, 'a', encoding='utf-8') as f:
        f.write(f"{url}\t{pub_day.isoformat()}\n")
    added += 1

# Fallback: fetch daily archive pages for dates with few URLs
def fetch_archive(day):
    url = f"https://www.suaramerdeka.com/arsip/{day.year:04d}/{day.month:02d}/{day.day:02d}"
    st, txt, _ = fetch(url)
    if st != 200:
        return []
    links = re.findall(r'href="(https://www\.suaramerdeka\.com/[^\"]+)"', txt)
    # Heuristic: article URLs contain a long numeric segment (e.g., /1234567/)
    article_links = [l for l in links if re.search(r'/\d{7,}/', l)]
    return article_links

current = START
while current <= END:
    if counts.get(current, 0) < 15:
        for art_url in fetch_archive(current):
            key = (art_url, current.isoformat())
            if key in seen:
                continue
            seen.add(key)
            with open(out_path, 'a', encoding='utf-8') as f:
                f.write(f"{art_url}\t{current.isoformat()}\n")
            counts.setdefault(current, 0)
            counts[current] += 1
            added += 1
            if counts[current] >= 15:
                break
    current += datetime.timedelta(days=1)

print(f"Finished. Added {added} URLs.")
for d in sorted(counts):
    print(f"{d}\t{counts[d]}")
