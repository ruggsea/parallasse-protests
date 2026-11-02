#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET
from urllib.parse import urljoin

# Add path for polite_fetch helper (project-relative)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write('polite_fetch not found\n')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = 'https://www.lacuarta.com/arc/outboundfeeds/sitemap/?outputType=xml'
STEP = 100

def parse_date(dt_str):
    # dt_str like 2026-10-26T16:12:25.858Z
    try:
        return datetime.datetime.strptime(dt_str[:10], '%Y-%m-%d').date()
    except Exception:
        return None

def fetch_chunk(offset):
    url = BASE if offset == 0 else f"{BASE}&from={offset}"
    status, text, _ = fetch(url)
    if status != 200:
        return None, status
    return text, status

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'lacuarta-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    seen = set()
    per_day = {}
    url_date = {}
    offset = 0
    while True:
        xml_text, status = fetch_chunk(offset)
        if xml_text is None:
            print(f'Stopped fetching at offset {offset}, HTTP {status}', file=sys.stderr)
            break
        root = ET.fromstring(xml_text)
        # namespace handling
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = root.findall('ns:url', ns)
        if not urls:
            # maybe no namespace
            urls = root.findall('url')
        min_date_in_chunk = None
        for u in urls:
            loc_el = u.find('ns:loc', ns) or u.find('loc')
            lastmod_el = u.find('ns:lastmod', ns) or u.find('lastmod')
            if loc_el is None or lastmod_el is None:
                continue
            url = loc_el.text.strip()
            date = parse_date(lastmod_el.text.strip())
            if date is None:
                continue
            if min_date_in_chunk is None or date < min_date_in_chunk:
                min_date_in_chunk = date
            if START <= date <= END:
                if url not in seen:
                    seen.add(url)
                    per_day.setdefault(date, 0)
                    per_day[date] += 1
                    url_date[url] = date
        # If the oldest entry in this chunk is before START, we can stop after processing
        if min_date_in_chunk and min_date_in_chunk < START:
            break
        offset += STEP
    # Write TSV sorted by date then url
    with open(out_path, 'w', encoding='utf-8') as f:
        for date in sorted(per_day):
            # gather urls for this date
            # filter seen list by date again (simple re-iteration not stored)
            pass
    # Since we didn't keep mapping of url->date, re-parse to write
    # Simpler: store mapping during loop
    # (Rewriting above) 

if __name__ == '__main__':
    main()
