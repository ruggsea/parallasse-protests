#!/usr/bin/env python3
import sys, os, csv, datetime, json, xml.etree.ElementTree as ET
from pathlib import Path

# Ensure the polite_fetch module path is added
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# The repo adds a package directory 'scrapers' to PYTHONPATH in other scripts; we follow that convention
# Import fetch respecting robots.txt, rate‑limits, logging
from polite_fetch import fetch

SITEMAP_URL = "https://www.ecuadortv.ec/sitemap.xml"
CDX_URL = "http://web.archive.org/cdx/search/cdx?url=www.ecuadortv.ec/*&from=20260925&to=20261025&output=json&collapse=urlkey"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_sitemap(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: status {status}")
    return text

def parse_sitemap(xml_text: str):
    # ET can handle namespaces; we only need loc and lastmod
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        # lastmod may contain timezone offset; split at 'T'
        date_part = lastmod_el.text.strip().split('T')[0]
        try:
            pub_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            continue
        yield url, pub_date

def fetch_cdx(url: str) -> list:
    """Fetch Wayback CDX JSON and return list of (url, date) tuples for news articles."""
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed CDX fetch {url}: status {status}", file=sys.stderr)
        return []
    try:
        data = json.loads(text)
    except Exception as e:
        print(f"CDX JSON parse error: {e}", file=sys.stderr)
        return []
    results = []
    # data is list of rows, first row is header
    for row in data[1:]:
        # fields: urlkey, timestamp, original, mimetype, statuscode, digest, length
        if len(row) < 5:
            continue
        original = row[2]
        statuscode = row[4]
        if statuscode != "200":
            continue
        if "/noticias/" not in original:
            continue
        timestamp = row[1]
        # timestamp format YYYYMMDDhhmmss
        date_str = timestamp[:8]
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            continue
        results.append((original, date_obj))
    return results

def main():
    try:
        xml = fetch_sitemap(SITEMAP_URL)
    except Exception as e:
        print(f"Error fetching sitemap: {e}", file=sys.stderr)
        sys.exit(1)
    # Collect URLs in date range
    per_day = {}
    for url, pub_date in parse_sitemap(xml):
        if START <= pub_date <= END:
            per_day.setdefault(pub_date, set()).add(url)

    # Ensure we have at least 15 URLs for the required sample dates.
    target_dates = [datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)]
    need_dates = [d for d in target_dates if len(per_day.get(d, set())) < 15]
    if need_dates:
        cdx_items = fetch_cdx(CDX_URL)
        for url, d in cdx_items:
            if d in need_dates:
                per_day.setdefault(d, set()).add(url)
                # Stop adding once we have enough for that day
                if len(per_day[d]) >= 15:
                    need_dates.remove(d)
        # Note: if still insufficient after CDX, we will report low volume later.

    # Write TSV
    # Determine repository root (two directories up from this script's directory)
    repo_root = Path(__file__).resolve().parent.parent.parent
    out_path = repo_root / 'data' / 'urls_custom' / 'ecuadortv-ec.tsv'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for day in sorted(per_day):
            for u in sorted(per_day[day]):
                writer.writerow([u, day.isoformat()])
                total += 1
    # Print counts per day
    for day in sorted(per_day):
        print(f"{day}: {len(per_day[day])} URLs")
    print(f"Total URLs written: {total}")

if __name__ == "__main__":
    main()
