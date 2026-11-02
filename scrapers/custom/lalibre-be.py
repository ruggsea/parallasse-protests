import sys
import os
import re
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

BASE_SITEMAP = 'https://www.lalibre.be/arc/outboundfeeds/sitemap/?outputType=xml'
PAGE_SIZE = 100  # each sitemap page contains up to 100 URLs

def parse_date_from_url(url: str) -> datetime.date:
    """Extract YYYY/MM/DD from the URL if present, else return None."""
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None

def fetch_sitemap(offset: int = 0):
    url = BASE_SITEMAP if offset == 0 else f"{BASE_SITEMAP}&from={offset}"
    status, txt, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: status {status}")
    return txt

def extract_urls(txt: str):
    root = ET.fromstring(txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for el in root.findall('ns:url', ns):
        loc = el.find('ns:loc', ns).text.strip()
        lastmod_el = el.find('ns:lastmod', ns)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None else None
        yield loc, lastmod

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'lalibre-be.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    seen = {}
    offset = 0
    while True:
        txt = fetch_sitemap(offset)
        # Parse dates in this page to decide when to stop
        page_dates = []
        for loc, lastmod in extract_urls(txt):
            pub_date = parse_date_from_url(loc)
            if not pub_date and lastmod:
                try:
                    pub_date = datetime.datetime.fromisoformat(lastmod.replace('Z', '+00:00')).date()
                except Exception:
                    continue
            if not pub_date:
                continue
            page_dates.append(pub_date)
            if START <= pub_date <= END:
                if loc not in seen:
                    seen[loc] = pub_date.isoformat()
        # Determine if we can stop: if the newest date in this page is older than START, further pages will only be older.
        if page_dates:
            newest = max(page_dates)
            if newest < START:
                break
        else:
            # No URLs parsed at all – likely end of sitemap.
            break
        offset += PAGE_SIZE
    # Write TSV
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(seen.items()):
            f.write(f"{url}\t{date}\n")
    # Print per‑day counts
    day_counts = {}
    for d in seen.values():
        day_counts[d] = day_counts.get(d, 0) + 1
    for day in sorted(day_counts):
        print(f"{day}: {day_counts[day]} URLs")

if __name__ == '__main__':
    main()
