#!/usr/bin/env python3
import os, sys, datetime, xml.etree.ElementTree as ET
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
SITEMAP_URL = "https://www.elespectador.com/arc/outboundfeeds/news-sitemap/?outputType=xml"

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch sitemap {url}: status {status}\n")
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url in root.findall('ns:url', ns):
        loc_el = url.find('ns:loc', ns)
        news_date_el = url.find('.//news:publication_date', ns)
        if loc_el is None or news_date_el is None:
            continue
        loc = loc_el.text.strip()
        pub_dt = news_date_el.text.strip()
        # date part only
        try:
            pub_date = datetime.datetime.fromisoformat(pub_dt.rstrip('Z')).date()
        except Exception:
            continue
        entries.append((loc, pub_date))
    return entries

def main():
    xml = fetch_sitemap(SITEMAP_URL)
    entries = parse_sitemap(xml)
    # filter by date range
    filtered = [(u, d) for u, d in entries if START <= d <= END]
    # ensure unique URLs
    seen = set()
    uniq = []
    for u, d in filtered:
        if u not in seen:
            seen.add(u)
            uniq.append((u, d))
    # group by date for reporting
    per_day = {}
    for u, d in uniq:
        per_day.setdefault(d, []).append(u)
    # write TSV
    out_path = os.path.join('data', 'urls_custom', 'elespectador-com.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in sorted(uniq, key=lambda x: (x[1], x[0])):
            f.write(f"{u}\t{d.isoformat()}\n")
    # print counts per day
    for day in (START + datetime.timedelta(days=i) for i in range((END-START).days+1)):
        count = len(per_day.get(day, []))
        print(f"{day}: {count} URLs")

if __name__ == "__main__":
    main()
