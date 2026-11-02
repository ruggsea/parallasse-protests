#!/usr/bin/env python3
import sys, os, re, csv, datetime, time
from urllib.parse import urljoin

# Add path for polite_fetch (as per project convention)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

BASE = 'https://espresso.repubblica.it'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'espresso-repubblica-it.tsv'))
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + datetime.timedelta(n)

def fetch_sitemap_index():
    # common sitemap index locations
    candidates = [
        urljoin(BASE, '/sitemap-index.xml'),
        urljoin(BASE, '/sitemap.xml'),
        urljoin(BASE, '/sitemap-news.xml'),
    ]
    for url in candidates:
        status, text, _ = fetch(url)
        if status == 200 and '<sitemap>' in text:
            return text
    return None

def parse_sitemap_index(xml):
    # very simple extraction of <loc> entries
    locs = re.findall(r'<loc>(.*?)</loc>', xml)
    return locs

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status == 200:
        return text
    return None

def parse_urlset(xml):
    # extract <loc> and optional <lastmod>
    urls = []
    for entry in re.finditer(r'<url>(.*?)</url>', xml, re.DOTALL):
        block = entry.group(1)
        loc_match = re.search(r'<loc>(.*?)</loc>', block)
        if not loc_match:
            continue
        loc = loc_match.group(1).strip()
        lastmod_match = re.search(r'<lastmod>(.*?)</lastmod>', block)
        date = None
        if lastmod_match:
            date = lastmod_match.group(1)[:10]
        urls.append((loc, date))
    return urls

def date_from_url(url):
    # pattern /YYYY/MM/DD/ in path
    m = re.search(r'/([12][0-9]{3})/(0[1-9]|1[0-2])/([0-3][0-9])/', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

def collect_via_sitemaps():
    idx_xml = fetch_sitemap_index()
    if not idx_xml:
        return []
    sitemap_urls = parse_sitemap_index(idx_xml)
    collected = []
    for sm_url in sitemap_urls:
        sm_xml = fetch_sitemap(sm_url)
        if not sm_xml:
            continue
        for loc, lastmod in parse_urlset(sm_xml):
            if not loc.startswith(BASE):
                continue
            d = lastmod or date_from_url(loc)
            if d:
                try:
                    ddate = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                except ValueError:
                    continue
                if START <= ddate <= END:
                    collected.append((loc, ddate.isoformat()))
    return collected

def collect_via_wayback():
    # fallback using Wayback CDX for each day
    collected = []
    for day in daterange(START, END):
        ts = day.strftime('%Y%m%d')
        query = f"https://web.archive.org/cdx/search/cdx?url=espresso.repubblica.it/*&from={ts}&to={ts}&output=json&collapse=urlkey"
        status, text, _ = fetch(query)
        if status != 200:
            continue
        try:
            import json
            rows = json.loads(text)
        except Exception:
            continue
        # rows format: [ [field...], ... ] first row is header
        for row in rows[1:]:
            url = row[2]
            # try to extract date from url path
            d = date_from_url(url)
            if d:
                try:
                    ddate = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                except ValueError:
                    continue
                if START <= ddate <= END:
                    collected.append((url, ddate.isoformat()))
    return collected

def main():
    result = collect_via_sitemaps()
    if not result:
        result = collect_via_wayback()
    # deduplicate
    uniq = {}
    for u, d in result:
        uniq[u] = d
    # write TSV
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for u, d in sorted(uniq.items()):
            writer.writerow([u, d])
    # per‑day counts
    counts = {}
    for _, d in uniq.items():
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")

if __name__ == '__main__':
    main()
