#!/usr/bin/env python3
"""Cooperativa.cl custom scraper.
Collect article URLs published between 2026-09-25 and 2026-10-25.
Uses the site's news sitemap and the general paginated sitemap.
Writes TSV with URL and ISO date (YYYY-MM-DD)."""
import sys, os, datetime, xml.etree.ElementTree as ET
from collections import Counter

# Ensure polite_fetch is importable (relative to project root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_news_sitemap(text):
    """Parse sitemap_news.xml – use <news:publication_date>."""
    root = ET.fromstring(text)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    for url in root.findall('ns:url', ns):
        loc_el = url.find('ns:loc', ns)
        news_el = url.find('news:news', ns)
        if loc_el is None or news_el is None:
            continue
        pub_el = news_el.find('news:publication_date', ns)
        if pub_el is None:
            continue
        try:
            pub_dt = datetime.datetime.fromisoformat(pub_el.text)
        except Exception:
            continue
        pub_date = pub_dt.date()
        if START <= pub_date <= END:
            yield loc_el.text.strip(), pub_date.isoformat()

def parse_generic_sitemap(text):
    """Parse sitemap_pags.xml – use <lastmod> as publication date.
    Some entries may lack a proper date; they are skipped.
    """
    root = ET.fromstring(text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url in root.findall('ns:url', ns):
        loc_el = url.find('ns:loc', ns)
        lastmod_el = url.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        try:
            pub_date = datetime.datetime.strptime(lastmod_el.text.strip(), "%Y-%m-%d").date()
        except Exception:
            continue
        if START <= pub_date <= END:
            yield loc_el.text.strip(), pub_date.isoformat()

entries = []
# 1. News sitemap
status, txt, _ = fetch('https://www.cooperativa.cl/noticias/sitemap_news.xml')
if status == 200:
    entries.extend(parse_news_sitemap(txt))
else:
    print('Failed news sitemap fetch', status, file=sys.stderr)

# 2. Generic sitemap (covers many URLs)
status, txt, _ = fetch('https://www.cooperativa.cl/noticias/sitemap_pags.xml')
if status == 200:
    entries.extend(parse_generic_sitemap(txt))
else:
    print('Failed generic sitemap fetch', status, file=sys.stderr)

# Deduplicate while preserving first occurrence (date from earlier source wins)
seen = set()
unique = []
for url, date in entries:
    if url not in seen:
        seen.add(url)
        unique.append((url, date))

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'cooperativa-cl.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for u, d in unique:
        f.write(f"{u}\t{d}\n")

# Print per‑day counts
cnt = Counter(d for _, d in unique)
for single in (START + datetime.timedelta(days=i) for i in range((END - START).days + 1)):
    ds = single.isoformat()
    print(f"{ds}: {cnt.get(ds, 0)} URLs")

print('Total URLs written:', len(unique))
