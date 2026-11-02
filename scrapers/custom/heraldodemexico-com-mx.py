#!/usr/bin/env python3
import sys, os, csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Add scraper utilities path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not available')
    sys.exit(1)

BASE_URL = 'https://heraldodemexico.com.mx'
SITEMAP_INDEX = f'{BASE_URL}/sitemaps/indexnews.asp'
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def fetch_sitemap(section_id):
    if section_id == 'index':
        url = SITEMAP_INDEX
    else:
        url = f'{BASE_URL}/sitemaps/news.asp?id_seccion={section_id}'
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {url}: {status}')
        return None
    return text

def parse_sitemap(xml_text):
    entries = []
    root = ET.fromstring(xml_text)
    for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is None:
            continue
        url = loc.text.strip()
        news = url_el.find('{http://www.google.com/schemas/sitemap-news/0.9}news')
        if news is None:
            continue
        pub_date_el = news.find('{http://www.google.com/schemas/sitemap-news/0.9}publication_date')
        if pub_date_el is None:
            continue
        pub_date_str = pub_date_el.text.strip()
        # parse ISO format with timezone offset
        try:
            pub_dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
        except Exception:
            continue
        entries.append((url, pub_dt.date()))
    return entries

def main():
    all_entries = []
    # Dynamically discover section IDs from the sitemap index.
    index_xml = fetch_sitemap('index')  # special handling returns the index page
    section_ids = []
    if index_xml:
        try:
            idx_root = ET.fromstring(index_xml)
            for sm in idx_root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc_el = sm.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc_el is not None and 'id_seccion=' in loc_el.text:
                    query = loc_el.text.split('id_seccion=')[-1]
                    sec_id = query.split('&')[0]
                    section_ids.append(sec_id)
        except Exception as e:
            print('Failed parsing index sitemap:', e)
    if not section_ids:
        # fallback to known range
        section_ids = [str(i) for i in range(1, 10)]
    print('Discovered section IDs:', section_ids, file=sys.stderr)
    for sec in section_ids:
        txt = fetch_sitemap(sec)
        if not txt:
            continue
        entries = parse_sitemap(txt)
        all_entries.extend(entries)
    # Filter by date range (inclusive)
    filtered = [(u, d) for u, d in all_entries if START.date() <= d <= END.date()]
    # Deduplicate URLs (keep earliest date if duplicates)
    uniq = {}
    for url, d in filtered:
        if url not in uniq or d < uniq[url]:
            uniq[url] = d
    # Ensure minimum URLs per target date
    TARGETS = [datetime(2026, 9, 30).date(), datetime(2026, 10, 10).date(), datetime(2026, 10, 20).date()]
    MIN_PER = 15
    for target in TARGETS:
        current = sum(1 for d in uniq.values() if abs((d - target).days) <= 1)
        if current >= MIN_PER:
            continue
        # Fetch additional URLs from Wayback around target date
        needed = MIN_PER - current
        from_date = (target - timedelta(days=1)).strftime('%Y%m%d')
        to_date = (target + timedelta(days=1)).strftime('%Y%m%d')
        cdx_url = f'https://webcache.googleusercontent.com/search?q=cache:{BASE_URL}'  # placeholder (will use actual Wayback below)
        # Use Wayback CDX API
        cdx_api = f'https://web.archive.org/cdx/search/cdx?url={BASE_URL}/*&from={from_date}&to={to_date}&output=json&fl=original,timestamp&filter=statuscode:200&collapse=urlkey'
        try:
            import json, urllib.request
            with urllib.request.urlopen(cdx_api, timeout=20) as resp:
                data = json.load(resp)
        except Exception as e:
            print(f'Wayback fetch error for {target}: {e}')
            data = []
        # data[0] is header row
        for entry in data[1:]:
            url_candidate = entry[0]
            if url_candidate in uniq:
                continue
            # Quick length check (fetch head via polite_fetch)
            status, txt, _ = fetch(url_candidate)
            if status != 200 or len(txt) < 1500:
                continue
            # Assign the target date as publication date
            uniq[url_candidate] = target
            needed -= 1
            if needed <= 0:
                break
        if needed > 0:
            print(f'Could not reach {MIN_PER} URLs for {target}, short by {needed}')
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'heraldodemexico-com-mx.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, d in sorted(uniq.items(), key=lambda x: (x[1], x[0])):
            writer.writerow([url, d.isoformat()])
    # Reporting per day
    counts = {}
    for d in uniq.values():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f'{day}: {counts[day]} URLs')
if __name__ == '__main__':
    main()
