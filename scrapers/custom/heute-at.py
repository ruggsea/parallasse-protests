import sys
import os
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = '2026-09-25'
END = '2026-10-25'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'heute-at.tsv'))

NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}

def add_entry(url, date_str, seen, per_day, lines):
    if not (START <= date_str <= END):
        return
    if url in seen:
        return
    seen.add(url)
    per_day[date_str] += 1
    lines.append(f"{url}\t{date_str}\n")

def process_news_sitemap():
    url = 'https://www.heute.at/storage/sitemaps/sitemap_news.xml'
    status, txt, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch news sitemap {url}, status {status}', file=sys.stderr)
        return []
    root = ET.fromstring(txt)
    entries = []
    for el in root.findall('sm:url', NS):
        loc = el.find('sm:loc', NS)
        news = el.find('news:news', NS)
        if loc is None or news is None:
            continue
        pub = news.find('news:publication_date', NS)
        if pub is None:
            continue
        url = loc.text.strip()
        date_full = pub.text.strip().split('T')[0]
        entries.append((url, date_full))
    return entries

def process_generic_sitemaps(skip_url):
    index = 'https://www.heute.at/storage/sitemaps/sitemap.xml'
    status, txt, _ = fetch(index)
    if status != 200:
        print(f'Failed to fetch sitemap index {index}, status {status}', file=sys.stderr)
        return []
    idx_root = ET.fromstring(txt)
    entries = []
    for sm in idx_root.findall('sm:sitemap', NS):
        loc = sm.find('sm:loc', NS)
        if loc is None:
            continue
        sm_url = loc.text.strip()
        if sm_url == skip_url:
            continue
        s_status, s_txt, _ = fetch(sm_url)
        if s_status != 200:
            continue
        s_root = ET.fromstring(s_txt)
        for u in s_root.findall('sm:url', NS):
            loc_el = u.find('sm:loc', NS)
            if loc_el is None:
                continue
            url = loc_el.text.strip()
            # keep only article URLs (pattern /s/)
            if '/s/' not in url:
                continue
            lm = u.find('sm:lastmod', NS)
            if lm is None:
                continue
            date_full = lm.text.strip().split('T')[0]
            entries.append((url, date_full))
    return entries

def main():
    seen = set()
    per_day = defaultdict(int)
    lines = []

    # news sitemap (most recent entries)
    for url, d in process_news_sitemap():
        add_entry(url, d, seen, per_day, lines)

    # generic sitemaps for older dates
    for url, d in process_generic_sitemaps('https://www.heute.at/storage/sitemaps/sitemap_news.xml'):
        add_entry(url, d, seen, per_day, lines)

    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")

if __name__ == '__main__':
    main()
