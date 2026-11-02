#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Insert path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_NEWS = 'https://www.df.cl/noticias/site/sitemap_news.xml'
status, news_xml, _ = fetch(SITEMAP_NEWS)
if status != 200:
    print(f'Failed to fetch news sitemap {SITEMAP_NEWS}: status {status}', file=sys.stderr)
    sys.exit(1)
root = ET.fromstring(news_xml)
ns = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}
entries = []
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
        entries.append((pub_date, loc_el.text.strip()))

# Fetch paginated sitemaps (gz files) for Sep and Oct 2026
SITEMAP_PAGS_INDEX = 'https://www.df.cl/noticias/site/sitemap_pags.xml'
status, index_xml, _ = fetch(SITEMAP_PAGS_INDEX)
if status == 200:
    idx_root = ET.fromstring(index_xml)
    # namespace handling
    ns_idx = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for sm in idx_root.findall('ns:sitemap', ns_idx):
        loc_el = sm.find('ns:loc', ns_idx)
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        # Only months we need
        if any(month in loc for month in ['202609', '202610']):
            # fetch (already decompressed by fetch)
            status, gz_content, _ = fetch(loc)
            if status != 200:
                continue
            sm_root = ET.fromstring(gz_content)
            for url in sm_root.findall('ns:url', ns_idx):
                loc_u = url.find('ns:loc', ns_idx)
                lastmod_el = url.find('ns:lastmod', ns_idx)
                if loc_u is None or lastmod_el is None:
                    continue
                try:
                    lm_dt = datetime.datetime.fromisoformat(lastmod_el.text)
                except Exception:
                    continue
                lm_date = lm_dt.date()
                if START <= lm_date <= END:
                    entries.append((lm_date, loc_u.text.strip()))

# Deduplicate URLs, keep latest date if multiple (should be same)
unique = {}
for d, u in entries:
    unique[u] = d
print(f'Collected {len(unique)} unique URLs')
# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/df-cl.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, d in sorted(unique.items(), key=lambda x: (x[1], x[0])):
        f.write(f"{url}\t{d.isoformat()}\n")

# Print per‑day counts
from collections import Counter
cnt = Counter(unique.values())
for day in sorted(cnt):
    print(f"{day}: {cnt[day]} URLs")
