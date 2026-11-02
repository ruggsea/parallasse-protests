#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Add repository's scrapers directory to path for polite_fetch
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
scrapers_dir = os.path.join(repo_root, 'scrapers')
sys.path.insert(0, scrapers_dir)
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX = 'https://n1info.ba/sitemap.xml'

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: {status}', file=sys.stderr)
        return None
    return ET.fromstring(text)

def parse_sitemap(sitemap_url):
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    # Namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        # Try news:publication_date first, then fallback to lastmod
        date_el = url_el.find('news:news/news:publication_date', ns)
        if date_el is None:
            date_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or date_el is None:
            continue
        url = loc_el.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(date_el.text.strip())
        except Exception:
            # ignore unparsable dates
            continue
        date = dt.date()
        if START <= date <= END:
            entries.append((url, date.isoformat()))
    return entries

def main():
    # Gather all sitemap URLs from the index
    index_root = fetch_xml(SITEMAP_INDEX)
    if index_root is None:
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = []
    for sm in index_root.findall('ns:sitemap', ns):
        loc = sm.find('ns:loc', ns)
        if loc is not None and 'sitemap_post_' in loc.text:
            sitemap_urls.append(loc.text.strip())
    # also include the news sitemap which may not be listed in index
    sitemap_urls.append('https://n1info.ba/sitemap/sitemap_news_1.xml')

    all_entries = []
    seen = set()
    for sm_url in sitemap_urls:
        for url, date_str in parse_sitemap(sm_url):
            if url not in seen:
                seen.add(url)
                all_entries.append((url, date_str))

    # Sort by date then url
    all_entries.sort(key=lambda x: (x[1], x[0]))

    out_path = os.path.join(repo_root, 'data', 'urls_custom', 'n1info-ba.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date_str in all_entries:
            f.write(f"{url}\t{date_str}\n")

    # Print per‑day counts and total
    from collections import Counter
    cnt = Counter([d for _, d in all_entries])
    for day in sorted(cnt):
        print(f"{day}: {cnt[day]} URLs")
    print(f"Total URLs: {len(all_entries)}")

if __name__ == '__main__':
    main()
