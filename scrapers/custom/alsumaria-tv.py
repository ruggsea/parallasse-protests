import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# polite_fetch lives in the sibling scrapers directory
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = "https://www.alsumaria.tv/newssitemap.xml"

def iso_to_date(iso_str: str) -> datetime.date:
    return datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00')).date()

def fetch_sitemap(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: status {status}")
    return text

def parse_news_sitemap(xml_text: str):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if loc is None or pub_el is None:
            continue
        url = loc.text.strip()
        pub_date = iso_to_date(pub_el.text.strip())
        if START <= pub_date <= END:
            yield url, pub_date

def fetch_cdx(start: datetime.date, end: datetime.date):
    base = "https://web.archive.org/cdx/search/cdx"
    params = f"?url=alsumaria.tv/*&from={start.isoformat().replace('-','')}&to={end.isoformat().replace('-','')}&output=json&collapse=urlkey"
    url = base + params
    for attempt in range(5):
        status, text, _ = fetch(url)
        if status == 200:
            break
        import time; time.sleep(1)
    else:
        # Give up silently – no data will be added for this range
        return []
    import json as _json
    rows = _json.loads(text)
    for row in rows[1:]:
        orig = row[2]
        ts = row[1]
        try:
            pub_date = datetime.datetime.strptime(ts[:8], "%Y%m%d").date()
        except Exception:
            continue
        if START <= pub_date <= END:
            yield orig, pub_date

def main():
    collected = {}
    # Try news sitemap first
    try:
        xml = fetch_sitemap(SITEMAP_URL)
        for u, d in parse_news_sitemap(xml):
            collected.setdefault(d, set()).add(u)
    except Exception as e:
        print(f"Sitemap error: {e}", file=sys.stderr)
    # Fill missing dates via Wayback CDX (need >=15 URLs per day)
    all_dates = [START + datetime.timedelta(days=i) for i in range((END-START).days + 1)]
    missing = [d for d in all_dates if len(collected.get(d, [])) < 15]
    if missing:
        # retrieve each missing day individually to avoid large CDX timeouts
        for d in missing:
            for u, dd in fetch_cdx(d, d):
                collected.setdefault(dd, set()).add(u)
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'alsumaria-tv.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for day in sorted(collected):
            for url in sorted(collected[day]):
                f.write(f"{url}\t{day.isoformat()}\n")
    for day in sorted(collected):
        print(f"{day.isoformat()}: {len(collected[day])} URLs")

if __name__ == "__main__":
    main()
