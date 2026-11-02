#!/usr/bin/env python3
"""Scrape article URLs from The Saturday Paper (Australia).
Collect URLs published between 2026-09-25 and 2026-10-25 (inclusive).
Writes a TSV file data/urls_custom/thesaturdaypaper-com-au.tsv with
`URL<TAB>YYYY-MM-DD` (date taken from the URL path when available, otherwise
from the sitemap entry). Also prints per‑day counts.
All HTTP requests use `polite_fetch.fetch` which respects robots.txt.
"""
import sys
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime

# make polite_fetch importable (scrapers/ is added to sys.path by other scripts)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch not found\n')
    sys.exit(1)

BASE = 'https://www.thesaturdaypaper.com.au'
SITEMAP_INDEX = f'{BASE}/sitemap.xml'
START = date(2026, 9, 25)
END = date(2026, 10, 25)

def fetch_xml(url):
    status, txt, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f'Failed {url}: {status}\n')
        return None
    return ET.fromstring(txt)

# Namespace helpers
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9',
      'news': 'http://www.google.com/schemas/sitemap-news/0.9'}

urls_by_date = {}
seen = set()

# 1. Article sitemaps (contain date in URL path)
index_root = fetch_xml(SITEMAP_INDEX)
if not index_root:
    sys.exit(1)
article_sitemaps = []
for sm in index_root.findall('s:sitemap', NS):
    loc = sm.find('s:loc', NS)
    if loc is not None and 'articles-' in loc.text:
        article_sitemaps.append(loc.text)

for sm_url in article_sitemaps:
    root = fetch_xml(sm_url)
    if not root:
        continue
    for u in root.findall('s:url', NS):
        loc_el = u.find('s:loc', NS)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        if url in seen:
            continue
        # Extract date from URL /YYYY/MM/DD/
        parts = url.split('/')
        try:
            y, m, d = int(parts[-4]), int(parts[-3]), int(parts[-2])
            pub = date(y, m, d)
        except Exception:
            continue
        if not (START <= pub <= END):
            continue
        seen.add(url)
        datestr = pub.isoformat()
        urls_by_date.setdefault(datestr, []).append(url)

# 2. News sitemap – uses <news:publication_date>
news_root = fetch_xml(f'{BASE}/sitemaps/news.xml')
if news_root is not None:
    for u in news_root.findall('s:url', NS):
        loc_el = u.find('s:loc', NS)
        news_pub = u.find('news:news/news:publication_date', NS)
        if loc_el is None or news_pub is None:
            continue
        url = loc_el.text.strip()
        if url in seen:
            continue
        try:
            pub_dt = datetime.fromisoformat(news_pub.text.strip())
            pub = pub_dt.date()
        except Exception:
            continue
        if not (START <= pub <= END):
            continue
        seen.add(url)
        datestr = pub.isoformat()
        urls_by_date.setdefault(datestr, []).append(url)

# 3. Posts sitemap – fallback to <lastmod>
posts_root = fetch_xml(f'{BASE}/sitemaps/posts.xml')
if posts_root is not None:
    for u in posts_root.findall('s:url', NS):
        loc_el = u.find('s:loc', NS)
        lastmod_el = u.find('s:lastmod', NS)
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        if url in seen:
            continue
        try:
            dt = datetime.fromisoformat(lastmod_el.text.strip())
            pub = dt.date()
        except Exception:
            continue
        if not (START <= pub <= END):
            continue
        seen.add(url)
        datestr = pub.isoformat()
        urls_by_date.setdefault(datestr, []).append(url)

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thesaturdaypaper-com-au.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as out_f:
    for d in sorted(urls_by_date):
        for u in sorted(urls_by_date[d]):
            out_f.write(f"{u}\t{d}\n")

# Wayback CDX fallback – always fetch and add any URLs not already seen
cdx_url = f'https://web.archive.org/cdx/search/cdx?url=www.thesaturdaypaper.com.au/*&from=20260925&to=20261025&output=json&collapse=urlkey'
status, text, _ = fetch(cdx_url)
if status == 200:
    import json
    try:
        rows = json.loads(text)
        for row in rows[1:]:  # skip header
            url = row[2]
            parts = url.split('/')
            if len(parts) < 5:
                continue
            try:
                y, m, d = int(parts[-4]), int(parts[-3]), int(parts[-2])
                pub = date(y, m, d)
            except Exception:
                continue
            if not (START <= pub <= END):
                continue
            if url in seen:
                continue
            seen.add(url)
            datestr = pub.isoformat()
            urls_by_date.setdefault(datestr, []).append(url)
    except Exception as e:
        sys.stderr.write(f'Wayback CDX parse error: {e}\n')

# Print per‑day counts after fallback
for d in sorted(urls_by_date):
    print(f"{d}: {len(urls_by_date[d])} URLs")
