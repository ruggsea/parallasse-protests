#!/usr/bin/env python3
import sys, os, re, json, datetime, time
from urllib.parse import urljoin

# Add the scrapers directory to sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not available', file=sys.stderr)
    sys.exit(1)

BASE = 'https://thetyee.ca'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thetyee-ca.tsv'))

def parse_date_from_url(url):
    # Look for /YYYY/MM/DD/ pattern in URL
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None
    return text

def extract_from_sitemap(xml_text):
    import xml.etree.ElementTree as ET
    urls = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return urls
    # support both sitemapindex and urlset
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        if loc is None or not loc.text:
            continue
        url = loc.text.strip()
        lastmod_el = url_el.find('ns:lastmod', ns)
        date = None
        if lastmod_el is not None and lastmod_el.text:
            try:
                date = datetime.datetime.fromisoformat(lastmod_el.text.strip()[:10]).date()
            except Exception:
                date = None
        if not date:
            date = parse_date_from_url(url)
        if date and START <= date <= END:
            urls.append((url, date))
    return urls

def fetch_wayback_cdx():
    # Use CDX API; respect rate limit by sleeping 1s per request
    cdx_url = f'https://web.archive.org/cdx/search/cdx?url=thetyee.ca/*&from=20260925&to=20261025&output=json&collapse=urlkey'
    status, text, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    # first row is header
    entries = []
    for row in data[1:]:
        # columns: urlkey, timestamp, original, mime, statuscode, checksum, length, offset, filename
        original = row[2]
        ts = row[1]  # YYYYMMDDhhmmss
        try:
            date = datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
        except Exception:
            continue
        if START <= date <= END:
            entries.append((original, date))
    return entries

def fetch_weekly_archive(url):
    status, text, _ = fetch(url)
    if status != 200:
        return []
    # Find all hrefs that are full URLs on thetyee.ca
    raw_links = re.findall(r'href="([^\"]+)"', text)
    links = []
    for l in raw_links:
        # Resolve relative URLs to absolute
        if l.startswith('http'):
            links.append(l)
        else:
            links.append(urljoin(BASE, l))
    entries = []
    for link in links:
        date = parse_date_from_url(link)
        if date and START <= date <= END:
            entries.append((link, date))
    return entries

def main():
    all_entries = {}
    # Try known sitemap URLs first (often missing)
    sitemap_candidates = [
        urljoin(BASE, 'sitemap.xml'),
        urljoin(BASE, 'sitemap-news.xml'),
        urljoin(BASE, 'sitemap_index.xml'),
        urljoin(BASE, 'sitemap-index.xml'),
    ]
    for sm_url in sitemap_candidates:
        txt = fetch_sitemap(sm_url)
        if txt:
            for url, date in extract_from_sitemap(txt):
                all_entries[url] = date
    # If still empty, use weekly archive pages
    if not all_entries:
        weekly_urls = [
            f"{BASE}/Archive/weekly/2026/09/21/",
            f"{BASE}/Archive/weekly/2026/10/05/",
            f"{BASE}/Archive/weekly/2026/10/19/",
        ]
        for wurl in weekly_urls:
            for url, date in fetch_weekly_archive(wurl):
                all_entries[url] = date
    # If still empty, fallback to Wayback CDX
    if not all_entries:
        for url, date in fetch_wayback_cdx():
            all_entries[url] = date
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as out:
        for url, date in sorted(all_entries.items()):
            out.write(f"{url}\t{date.isoformat()}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter([d.isoformat() for d in all_entries.values()])
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
