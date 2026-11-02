import sys, os, re, json, gzip
from datetime import datetime, timedelta
from urllib.parse import urlparse

# add polite_fetch path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # scrapers directory
try:
    from polite_fetch import fetch
except ImportError:
    raise RuntimeError('polite_fetch not found')

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'lesoir-be.tsv'))

def parse_date_from_url(url):
    # Try YYYY/MM/DD pattern
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Try YYYY-MM-DD pattern
    m = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None

def fetch_robots():
    status, text, _ = fetch('https://www.lesoir.be/robots.txt')
    return status, text

def extract_sitemaps(robots_text):
    sitemaps = []
    for line in robots_text.splitlines():
        if line.lower().startswith('sitemap:'):
            url = line.split(':', 1)[1].strip()
            sitemaps.append(url)
    return sitemaps

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None
    # handle gzip if .gz suffix
    if url.endswith('.gz'):
        try:
            data = gzip.decompress(text.encode('utf-8'))
        except Exception:
            data = text.encode('utf-8')
        return data
    return text.encode('utf-8')

def parse_sitemap(content_bytes):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content_bytes)
    except ET.ParseError:
        return []
    ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    urls = []
    for url_el in root.findall('.//ns:url', ns) if ns else root.findall('.//url'):
        loc_el = url_el.find('ns:loc', ns) if ns else url_el.find('loc')
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod_el = url_el.find('ns:lastmod', ns) if ns else url_el.find('lastmod')
        date = None
        if lastmod_el is not None and lastmod_el.text:
            try:
                date = datetime.fromisoformat(lastmod_el.text.strip()[:10])
            except Exception:
                pass
        if date is None:
            date = parse_date_from_url(loc)
        urls.append((loc, date))
    return urls

def wayback_cdx():
    # Use Wayback CDX API via polite_fetch
    cdx_url = (
        'https://web.archive.org/cdx/search/cdx?url=lesoir.be/*'
        f'&from={START.strftime('%Y%m%d')}'
        f'&to={END.strftime('%Y%m%d')}'
        '&output=json&collapse=urlkey'
    )
    status, text, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    # First entry is field names
    results = []
    for row in data[1:]:
        # columns: urlkey, timestamp, original, mime, statuscode, digest, length
        if len(row) < 3:
            continue
        url = row[2]
        ts = row[1]
        try:
            dt = datetime.strptime(ts, '%Y%m%d%H%M%S')
        except Exception:
            continue
        results.append((url, dt))
    return results

def main():
    urls_dates = {}
    # Try sitemap route first
    status, robots = fetch_robots()
    sitemaps = []
    if status == 200:
        sitemaps = extract_sitemaps(robots)
    # Prefer news sitemaps; filter others out
    news_sitemaps = [u for u in sitemaps if 'sitemapnews' in u.lower()]
    archive_sitemaps = [u for u in sitemaps if 'archive' in u.lower() or 'sitemaparchives' in u.lower()]
    # If none of the above, fallback to any sitemap ending with .xml (excluding the index itself)
    if not news_sitemaps and not archive_sitemaps:
        news_sitemaps = [u for u in sitemaps if u.lower().endswith('.xml') and 'sitemap.xml' not in u.lower()]
    for sm in news_sitemaps + archive_sitemaps:
        content = fetch_xml(sm)
        if not content:
            continue
        for loc, date in parse_sitemap(content):
            if not loc or not date:
                continue
            if START <= date <= END:
                urls_dates[loc] = date.date().isoformat()
    # If we have less than 500 URLs, fallback to Wayback
    if len(urls_dates) < 500:
        for loc, dt in wayback_cdx():
            if not (START <= dt <= END):
                continue
            if loc not in urls_dates:
                urls_dates[loc] = dt.date().isoformat()
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, d in sorted(urls_dates.items()):
            f.write(f"{url}\t{d}\n")
    # Print per‑day counts for quick check
    from collections import Counter
    cnt = Counter(urls_dates.values())
    for day in sorted(cnt):
        print(f"{day}: {cnt[day]}")
    print(f"Total URLs written: {len(urls_dates)}")

if __name__ == '__main__':
    main()
