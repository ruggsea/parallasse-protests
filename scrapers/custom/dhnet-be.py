#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET, collections

# Ensure the polite_fetch module is on the path (project scrapers directory)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
SITEMAP_INDEX = "https://www.dhnet.be/arc/outboundfeeds/sitemap-index/?outputType=xml"

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"[WARN] fetch {url} returned status {status}", file=sys.stderr)
        return None
    return text

def parse_sitemap_index(text):
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(text)
    return [elem.find('ns:loc', ns).text for elem in root.findall('ns:sitemap', ns)]

def parse_sitemap(text):
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(text)
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        loc = loc_el.text
        lastmod_el = url_el.find('ns:lastmod', ns)
        if lastmod_el is None:
            continue
        # keep only date part YYYY-MM-DD
        date_str = lastmod_el.text.split('T')[0]
        try:
            d = datetime.date.fromisoformat(date_str)
        except Exception:
            continue
        entries.append((loc, d))
    return entries

def main():
    index_text = fetch_text(SITEMAP_INDEX)
    if not index_text:
        sys.exit(1)
    chunk_urls = parse_sitemap_index(index_text)
    # output TSV path relative to project root
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'dhnet-be.tsv') )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    seen = set()
    day_counts = collections.Counter()
    with open(out_path, 'w', encoding='utf-8') as out_f:
        for chunk_url in chunk_urls:
            txt = fetch_text(chunk_url)
            if not txt:
                continue
            for loc, d in parse_sitemap(txt):
                if START_DATE <= d <= END_DATE and loc not in seen:
                    seen.add(loc)
                    out_f.write(f"{loc}\t{d.isoformat()}\n")
                    day_counts[d.isoformat()] += 1
    # Print summary
    for day in sorted(day_counts):
        print(f"{day}: {day_counts[day]} URLs")

if __name__ == "__main__":
    main()
