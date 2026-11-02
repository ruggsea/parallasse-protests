#!/usr/bin/env python3
import sys, os, json, csv, datetime, time
from urllib.parse import urljoin

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

BASE = "https://www.manilatimes.net"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'manilatimes-net.tsv'))
os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)

def daterange(start, end):
    for n in range(int((end - start).days) + 1):
        yield start + datetime.timedelta(n)

def fetch_url(url):
    status, text, _ = fetch(url)
    return status, text

def parse_wp_sitemap(sitemap_url):
    """Fetch a WordPress sitemap index and return list of child sitemap URLs."""
    status, txt = fetch_url(sitemap_url)[:2]
    if status != 200:
        return []
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        return []
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [loc.text for loc in root.findall('.//sm:loc', ns)]

def extract_urls_from_sitemap(smap_url):
    status, txt = fetch_url(smap_url)[:2]
    if status != 200:
        return []
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        return []
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url in root.findall('.//sm:url', ns):
        loc = url.find('sm:loc', ns)
        lastmod = url.find('sm:lastmod', ns)
        if loc is None:
            continue
        u = loc.text.strip()
        d = None
        if lastmod is not None:
            try:
                d = datetime.datetime.fromisoformat(lastmod.text.strip()).date()
            except Exception:
                pass
        entries.append((u, d))
    return entries

def wayback_cdx():
    """Fallback: query Wayback CDX for URLs in date window."""
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx?url=manilatimes.net/*&from=20260925&to=20261025" 
        "&output=json&collapse=urlkey"
    )
    status, txt = fetch_url(cdx_url)[:2]
    if status != 200:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        return []
    # first line is field names
    rows = data[1:]
    urls = []
    for row in rows:
        url = row[2]
        timestamp = row[1]  # YYYYMMDDhhmmss
        try:
            d = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S").date()
        except Exception:
            d = None
        urls.append((url, d))
    return urls

def main():
    # 1. Try WP sitemap index
    sitemap_index = urljoin(BASE, 'wp-sitemap.xml')
    child_smaps = parse_wp_sitemap(sitemap_index)
    entries = []
    for sm in child_smaps:
        entries.extend(extract_urls_from_sitemap(sm))

    # Filter by date range using lastmod if present, otherwise infer from URL path /YYYY/MM/DD/
    results = {}
    for url, mod_date in entries:
        date = mod_date
        if date is None:
            # attempt to extract from URL pattern
            parts = url.split('/')
            # look for year/month/day pattern
            for i in range(len(parts)-2):
                try:
                    y = int(parts[i])
                    m = int(parts[i+1])
                    d = int(parts[i+2])
                    date = datetime.date(y, m, d)
                    break
                except Exception:
                    continue
        if date and START <= date <= END:
            results[url] = date

    # 2. If not enough URLs, fallback to Wayback CDX
    if len(results) < 100:  # arbitrary threshold
        for url, d in wayback_cdx():
            if d and START <= d <= END:
                results[url] = d

    # Write TSV (unique URLs)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for u, d in sorted(results.items(), key=lambda x: x[1]):
            writer.writerow([u, d.isoformat()])

    # Print per‑day counts
    counts = {date:0 for date in daterange(START, END)}
    for d in results.values():
        if d in counts:
            counts[d] += 1
    for date in sorted(counts):
        print(f"{date.isoformat()}: {counts[date]} URLs")

if __name__ == '__main__':
    main()
