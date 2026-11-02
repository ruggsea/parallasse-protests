import sys, os, re, datetime, json
from pathlib import Path
import sys, os, re, datetime, json
from pathlib import Path
import xml.etree.ElementTree as ET

# Add scrapers directory to path for polite_fetch import
BASE_DIR = Path(__file__).resolve().parent.parent  # .../scrapers
sys.path.insert(0, str(BASE_DIR))
from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

# Output TSV path (relative to repo root)
TSV_PATH = Path(__file__).resolve().parents[2] / 'data' / 'urls_custom' / 'citizen-digital.tsv'
TSV_PATH.parent.mkdir(parents=True, exist_ok=True)

def fetch_sitemap(url):
    """Fetch a sitemap and return list of (loc, lastmod) tuples."""
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap {url}: {status}')
        return []
    entries = []
    try:
        root = ET.fromstring(text)
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for url_el in root.findall('.//ns:url', ns):
            loc_el = url_el.find('ns:loc', ns)
            lastmod_el = url_el.find('ns:lastmod', ns)
            if loc_el is None:
                continue
            loc = loc_el.text.strip()
            lastmod = None
            if lastmod_el is not None and lastmod_el.text:
                # Parse ISO datetime with possible timezone offset
                try:
                    dt = datetime.datetime.fromisoformat(lastmod_el.text.strip())
                    lastmod = dt.date()
                except ValueError:
                    pass
            entries.append((loc, lastmod))
    except ET.ParseError as e:
        print(f'XML parse error for {url}: {e}')
    return entries

def main():
    sitemap_url = 'https://citizen.digital/sitemap-articles.xml'
    entries = fetch_sitemap(sitemap_url)
    print(f'Fetched {len(entries)} entries from sitemap')
    # Filter by date range using lastmod if available, otherwise fallback to fetching page
    results = {}
    for loc, pub_date in entries:
        if pub_date is None:
            # fallback: fetch page and try to extract date from HTML (rare)
            status, html, _ = fetch(loc)
            if status != 200:
                continue
            # simple fallback: look for date in meta tags
            m = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})', html)
            if m:
                try:
                    pub_date = datetime.datetime.strptime(m.group(1), '%Y-%m-%d').date()
                except ValueError:
                    continue
            else:
                continue
        if START_DATE <= pub_date <= END_DATE:
            results.setdefault(pub_date, set()).add(loc)
    # Write TSV output
    with TSV_PATH.open('w', encoding='utf-8') as f:
        for day in sorted(results):
            for url in sorted(results[day]):
                f.write(f"{url}\t{day.isoformat()}\n")
    # Print per‑day counts
    for day in sorted(results):
        print(f"{day}: {len(results[day])} URLs")

if __name__ == '__main__':
    main()
