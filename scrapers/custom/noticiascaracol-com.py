import sys
import os
import csv
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

SITEMAPS = [
    "https://www.noticiascaracol.com/sitemap-202609.xml",
    "https://www.noticiascaracol.com/sitemap-202610.xml",
]

def parse_date(dt_str: str) -> datetime.date:
    # dt_str like 2026-09-01T06:56:50-05:00
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
        return dt.date()
    except Exception:
        # fallback split
        return datetime.datetime.strptime(dt_str[:10], "%Y-%m-%d").date()

def fetch_sitemap(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: status {status}")
    return text

def main():
    entries = []  # list of (url, date_str)
    seen = set()
    for sm_url in SITEMAPS:
        try:
            xml_text = fetch_sitemap(sm_url)
        except Exception as e:
            print(e, file=sys.stderr)
            continue
        root = ET.fromstring(xml_text)
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for url_el in root.findall('ns:url', ns):
            loc_el = url_el.find('ns:loc', ns)
            lastmod_el = url_el.find('ns:lastmod', ns)
            if loc_el is None or lastmod_el is None:
                continue
            url = loc_el.text.strip()
            lastmod = lastmod_el.text.strip()
            pub_date = parse_date(lastmod)
            if START_DATE <= pub_date <= END_DATE:
                if url not in seen:
                    seen.add(url)
                    entries.append((url, pub_date.isoformat()))
        # End for each url
    # Sort entries by date then url
    entries.sort(key=lambda x: (x[1], x[0]))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'noticiascaracol-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, date_str in entries:
            writer.writerow([url, date_str])
    # Print per‑day counts
    counts = {}
    for _, d in entries:
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")

if __name__ == "__main__":
    main()
