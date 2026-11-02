#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure the project scrapers path is in sys.path for polite_fetch
scrapers_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if scrapers_path not in sys.path:
    sys.path.insert(0, scrapers_path)

from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://www.famigliacristiana.it/sitemaps/fc/sitemap_news1.xml"
RSS_URL = "https://www.famigliacristiana.it/sitemaps/fc/rss"

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch {url}: status {status}\n")
        return None
    return text

def parse_sitemap(xml_text):
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    url_elems = root.findall('sm:url', ns)
    result = []
    for ue in url_elems:
        loc_elem = ue.find('sm:loc', ns)
        news_pub_elem = ue.find('news:news/news:publication_date', ns)
        if loc_elem is None or news_pub_elem is None:
            continue
        url = loc_elem.text.strip()
        pub_iso = news_pub_elem.text.strip()
        try:
            pub_dt = datetime.datetime.fromisoformat(pub_iso.rstrip('Z'))
        except Exception:
            continue
        pub_date = pub_dt.date()
        if START <= pub_date <= END:
            result.append((url, pub_date.isoformat()))
    return result

def parse_rss(xml_text):
    import email.utils as eut
    root = ET.fromstring(xml_text)
    result = []
    for item in root.findall('.//item'):
        link = item.find('link')
        pub = item.find('pubDate')
        if link is None or pub is None:
            continue
        url = link.text.strip()
        try:
            dt = eut.parsedate_to_datetime(pub.text.strip())
        except Exception:
            continue
        pub_date = dt.date()
        if START <= pub_date <= END:
            result.append((url, pub_date.isoformat()))
    return result

def main():
    entries = []
    xml = fetch_xml(SITEMAP_URL)
    if xml:
        entries.extend(parse_sitemap(xml))
    rss = fetch_xml(RSS_URL)
    if rss:
        entries.extend(parse_rss(rss))
    # Deduplicate URLs keeping first date
    uniq = {}
    for url, date in entries:
        uniq.setdefault(url, date)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'famigliacristiana-it.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(uniq.items()):
            f.write(f"{url}\t{date}\n")
    from collections import Counter
    cnt = Counter(uniq.values())
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == "__main__":
    main()
