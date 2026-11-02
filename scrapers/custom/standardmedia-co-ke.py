#!/usr/bin/env python3
import sys, os
from datetime import datetime, date
import xml.etree.ElementTree as ET

# Polite fetch setup (adds repo to path)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START_DATE = date.fromisoformat('2026-09-25')
END_DATE   = date.fromisoformat('2026-10-25')

# Primary source: Google News sitemap (may be limited to recent items)
SITEMAP_URL = 'https://www.standardmedia.co.ke/sitemaps/googlenews.php'

# Fallback RSS feeds (different sections). Dates come from <pubDate>.
RSS_FEEDS = [
    'https://www.standardmedia.co.ke/rss/headlines.php',
    'https://www.standardmedia.co.ke/rss/kenya.php',
    'https://www.standardmedia.co.ke/rss/world.php',
    'https://www.standardmedia.co.ke/rss/politics.php',
    'https://www.standardmedia.co.ke/rss/entertainment.php',
]

NS_SITEMAP = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9',
}

def fetch_url(url):
    status, text, _ = fetch(url)
    return status, text

def parse_sitemap(text):
    entries = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return entries
    for url_el in root.findall('ns:url', NS_SITEMAP):
        loc = url_el.find('ns:loc', NS_SITEMAP)
        pub = url_el.find('news:news/news:publication_date', NS_SITEMAP)
        if loc is None or pub is None:
            continue
        url = loc.text.strip()
        try:
            pub_date = date.fromisoformat(pub.text.strip())
        except ValueError:
            continue
        if START_DATE <= pub_date <= END_DATE:
            entries.append((url, pub_date))
    return entries

def parse_rss(text):
    entries = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return entries
    for item in root.findall('.//item'):
        link_el = item.find('link')
        date_el = item.find('pubDate')
        if link_el is None or date_el is None:
            continue
        url = link_el.text.strip()
        # Example: Tue, 20 Oct 2026 12:15:56 +0300
        try:
            pub_dt = datetime.strptime(date_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z').date()
        except Exception:
            continue
        if START_DATE <= pub_dt <= END_DATE:
            entries.append((url, pub_dt))
    return entries

def collect_entries():
    all_entries = []
    # Try sitemap first
    status, txt = fetch_url(SITEMAP_URL)
    if status == 200 and txt:
        all_entries.extend(parse_sitemap(txt))
    # If not enough, add RSS feeds
    for feed in RSS_FEEDS:
        status, txt = fetch_url(feed)
        if status == 200 and txt:
            all_entries.extend(parse_rss(txt))
    return all_entries

def write_tsv(entries):
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/standardmedia-co-ke.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # deduplicate, keep earliest date if duplicate (should be same)
    uniq = {}
    for url, d in entries:
        uniq[url] = d
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(uniq.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{d.isoformat()}\n")
    # summary
    counts = {}
    for d in uniq.values():
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f"{d}: {counts[d]} URLs")
    print(f"Total URLs written: {len(uniq)}")

def main():
    entries = collect_entries()
    if not entries:
        sys.stderr.write('No entries collected.\n')
        return 1
    write_tsv(entries)
    return 0

if __name__ == '__main__':
    sys.exit(main())
