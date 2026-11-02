#!/usr/bin/env python3
import sys, os, re, csv, json, gzip, datetime, xml.etree.ElementTree as ET

# Add project lib path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://www.stern.de'
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def parse_date(date_str):
    # try ISO first
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            pass
    # fallback: extract YYYY-MM-DD from string
    m = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
    if m:
        return datetime.datetime.strptime(m.group(1), '%Y-%m-%d').date()
    return None

def fetch_robots_sitemaps():
    status, text, _ = fetch(BASE_URL + '/robots.txt')
    if status != 200:
        return []
    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith('sitemap:'):
            url = line.split(':', 1)[1].strip()
            sitemaps.append(url)
    return sitemaps

def fetch_sitemap(url):
    status, content, _ = fetch(url)
    if status != 200:
        return []
    # handle gzip if needed
    if url.endswith('.gz'):
        try:
            content = gzip.decompress(content.encode('utf-8'))
        except Exception:
            # content may be bytes already
            try:
                content = gzip.decompress(content)
            except Exception:
                pass
    # parse XML
    entries = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for url_el in root.findall('.//url'):
        loc = url_el.find('loc')
        if loc is None:
            continue
        loc_text = loc.text.strip()
        # try news:publication_date
        date_el = url_el.find('news:news/publication_date', ns)
        if date_el is None:
            date_el = url_el.find('lastmod')
        date_text = date_el.text.strip() if date_el is not None else ''
        entries.append((loc_text, date_text))
    return entries

def fetch_wayback_cdx():
    cdx_url = ('https://web.archive.org/cdx/search/cdx?url=stern.de/*'
               '&from=20260925&to=20261025&output=json&collapse=urlkey')
    status, txt, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        return []
    # first row is header
    entries = []
    for row in data[1:]:
        # format: [url, timestamp, ...]
        url = row[0]
        ts = row[1]
        # timestamp like YYYYMMDDhhmmss
        try:
            date = datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
        except Exception:
            continue
        entries.append((url, date.isoformat()))
    return entries

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'stern-de.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    urls = {}
    # Try sitemaps from robots.txt
    for sitemap_url in fetch_robots_sitemaps():
        for loc, date_str in fetch_sitemap(sitemap_url):
            d = parse_date(date_str)
            if d and START_DATE <= d <= END_DATE:
                urls[loc] = d.isoformat()
    # If still empty, fallback to Wayback CDX
    if not urls:
        for loc, date_str in fetch_wayback_cdx():
            d = parse_date(date_str)
            if d and START_DATE <= d <= END_DATE:
                urls[loc] = d.isoformat()
    # Write TSV
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, date in sorted(urls.items()):
            writer.writerow([url, date])
    # Print per‑day counts
    counts = {}
    for date in urls.values():
        counts[date] = counts.get(date, 0) + 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")

if __name__ == '__main__':
    main()
