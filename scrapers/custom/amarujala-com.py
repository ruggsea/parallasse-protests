#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable (scrapers directory is added by runner)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://www.amarujala.com/sitemap-news-v1.xml"
CDX_URL = "https://web.archive.org/cdx/search/cdx?url=www.amarujala.com/*&from=20260925&to=20261025&output=json&collapse=urlkey"

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch {url}: HTTP {status}\n")
        return None
    return text

def fetch_cdx(url):
    status, text, _ = fetch(url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch CDX {url}: HTTP {status}\n")
        return None
    return text

def parse_sitemap(xml_text):
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or pub_el is None:
            continue
        url = loc_el.text.strip()
        pub_dt = pub_el.text.strip()  # e.g. 2026-10-25T22:09:08+05:30
        try:
            pub_date = datetime.datetime.fromisoformat(pub_dt).date()
        except Exception:
            # fallback: take first 10 chars
            pub_date = datetime.date.fromisoformat(pub_dt[:10])
        entries.append((url, pub_date))
    return entries

def main():
    # First, try the news sitemap
    xml = fetch_sitemap(SITEMAP_URL)
    entries = []
    if xml:
        entries = parse_sitemap(xml)
    # Fallback: Wayback CDX for URLs containing a date in the slug
    cdx_text = fetch_cdx(CDX_URL)
    if cdx_text:
        try:
            import json, re
            cdx_data = json.loads(cdx_text)
            # First row is header
            for row in cdx_data[1:]:
                url = row[2]
                # Look for date pattern in URL slug
                m = re.search(r"-(\d{4}-\d{2}-\d{2})(?:/|$)", url)
                if m:
                    try:
                        pub_date = datetime.datetime.strptime(m.group(1), "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    entries.append((url, pub_date))
        except Exception as e:
            sys.stderr.write(f"Failed to parse CDX data: {e}\n")
    # Filter by date range and deduplicate (later dates win)
    uniq = {}
    for url, pub_date in entries:
        if START <= pub_date <= END:
            uniq[url] = pub_date
    # Group by date for reporting
    per_day = {}
    for url, date in uniq.items():
        per_day.setdefault(date, []).append(url)
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/amarujala-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(uniq.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{date.isoformat()}\n")
    # Print counts per day
    for day in sorted(per_day.keys()):
        print(f"{day}: {len(per_day[day])} URLs")

if __name__ == "__main__":
    main()
