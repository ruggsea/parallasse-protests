#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET
# Ensure polite_fetch is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from polite_fetch import fetch

SITEMAP_INDEX_URL = 'https://www.pulzo.com/sitemap.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_url(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f'Failed to fetch {url}, status {status}\n')
        sys.exit(1)
    return text

def get_sitemap_urls(index_xml):
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(index_xml)
    urls = []
    for sm in root.findall('ns:sitemap', ns):
        loc = sm.find('ns:loc', ns)
        if loc is not None:
            urls.append(loc.text.strip())
    return urls

def parse_sitemap(xml_content):
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    root = ET.fromstring(xml_content)
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is not None:
            pub_dt = pub_el.text.strip()
        else:
            # fallback to standard lastmod element
            lastmod_el = url_el.find('ns:lastmod', ns)
            if lastmod_el is None:
                continue
            pub_dt = lastmod_el.text.strip()
        loc = loc_el.text.strip()
        # take date part (ignore time if present)
        pub_date = pub_dt.split('T')[0]
        try:
            d = datetime.datetime.strptime(pub_date, '%Y-%m-%d').date()
        except ValueError:
            continue
        entries.append((d, loc))
    return entries

def main():
    # fetch sitemap index
    index_xml = fetch_url(SITEMAP_INDEX_URL)
    sitemap_urls = get_sitemap_urls(index_xml)
    # Include news sitemap which holds recent articles but may not be listed in the index
    sitemap_urls.append('https://www.pulzo.com/sitemapnews.xml')
    entries = []
    for sm_url in sitemap_urls:
        try:
            sm_xml = fetch_url(sm_url)
            entries.extend(parse_sitemap(sm_xml))
        except Exception as e:
            sys.stderr.write(f'Skipping {sm_url}: {e}\n')
            continue
    # filter by date range
    filtered = [(d, u) for d, u in entries if START <= d <= END]
    # dedupe
    seen = set()
    per_day = {}
    for d, u in filtered:
        if u in seen:
            continue
        seen.add(u)
        per_day.setdefault(d, []).append(u)
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'pulzo-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for d in sorted(per_day):
            for u in per_day[d]:
                f.write(f"{u}\t{d.isoformat()}\n")
    # print counts per day
    for d in sorted(per_day):
        print(f"{d.isoformat()}: {len(per_day[d])} URLs")

if __name__ == '__main__':
    main()
