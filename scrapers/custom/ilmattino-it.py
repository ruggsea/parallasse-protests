#!/usr/bin/env python3
import sys, os, datetime, json, xml.etree.ElementTree as ET

# Add project scrapers dir to path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://www.ilmattino.it/?sez=XML&p=MapNews"
CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?url=www.ilmattino.it/*"
    "&from=20260925&to=20261025&output=json&collapse=urlkey"
)

def iso_to_date(s: str) -> datetime.date | None:
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt.date()
    except Exception:
        return None

def parse_sitemap(xml_text: str) -> dict[datetime.date, list[str]]:
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    root = ET.fromstring(xml_text)
    out = {}
    seen = set()
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Prefer news:publication_date, fallback to lastmod
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is None:
            pub_el = url_el.find('ns:lastmod', ns)
        if pub_el is None:
            continue
        pub_date = iso_to_date(pub_el.text.strip())
        if pub_date is None:
            continue
        if not (START <= pub_date <= END):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.setdefault(pub_date, []).append(url)
    return out

def parse_cdx(json_text: str) -> dict[datetime.date, list[str]]:
    # CDX returns JSON array; first row is header ['url','timestamp',...]
    data = json.loads(json_text)
    if not data or not isinstance(data, list):
        return {}
    header = data[0]
    url_idx = header.index('url') if 'url' in header else 0
    ts_idx = header.index('timestamp') if 'timestamp' in header else 1
    out = {}
    seen = set()
    for row in data[1:]:
        url = row[url_idx]
        ts = row[ts_idx]  # format: YYYYMMDDhhmmss
        try:
            date = datetime.datetime.strptime(ts[:8], "%Y%m%d").date()
        except Exception:
            continue
        if not (START <= date <= END):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.setdefault(date, []).append(url)
    return out

def merge_counts(a: dict, b: dict) -> dict:
    for d, urls in b.items():
        a.setdefault(d, []).extend(urls)
    return a

def write_tsv(data: dict[datetime.date, list[str]], out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for day in sorted(data):
            for u in data[day]:
                f.write(f"{u}\t{day.isoformat()}\n")

def main():
    # First try sitemap
    urls_by_date = {}
    status, text, _ = fetch(SITEMAP_URL)
    if status == 200 and text:
        try:
            urls_by_date = parse_sitemap(text)
        except Exception as e:
            print('Sitemap parse error', e, file=sys.stderr)
    # Check coverage for required sample dates
    needed_dates = [datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)]
    missing = any(len(urls_by_date.get(d, [])) < 15 for d in needed_dates)
    if missing:
        # Fallback to Wayback CDX
        status, cdx_text, _ = fetch(CDX_URL)
        if status == 200 and cdx_text:
            try:
                cdx_data = parse_cdx(cdx_text)
                urls_by_date = merge_counts(urls_by_date, cdx_data)
            except Exception as e:
                print('CDX parse error', e, file=sys.stderr)
    # Deduplicate per day (already deduped globally)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'ilmattino-it.tsv'))
    write_tsv(urls_by_date, out_path)
    # Print per‑day counts
    for d in sorted(urls_by_date):
        print(f"{d}: {len(urls_by_date[d])} URLs")

if __name__ == '__main__':
    main()
