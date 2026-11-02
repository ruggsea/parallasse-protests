import sys, os, datetime, xml.etree.ElementTree as ET
# Ensure polite_fetch can be imported from the repository root
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

from datetime import datetime

SITEMAP_URL = "https://www.sueddeutsche.de/sitemapapp/sitemap/news"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "sueddeutsche-de.tsv"))
DATE_FMT = "%Y-%m-%d"
START = datetime.strptime("2026-09-25", DATE_FMT)
END = datetime.strptime("2026-10-25", DATE_FMT)

def iter_urls(xml_content: str):
    ns = {
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
        'xhtml': 'http://www.w3.org/1999/xhtml'
    }
    root = ET.fromstring(xml_content)
    for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        news_el = url_el.find('news:news', ns)
        if loc_el is None or news_el is None:
            continue
        date_el = news_el.find('news:publication_date', ns)
        if date_el is None:
            continue
        url = loc_el.text.strip()
        pub_date = datetime.strptime(date_el.text[:10], DATE_FMT)
        if START <= pub_date <= END:
            yield url, pub_date.strftime(DATE_FMT)

def main():
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    url_to_date = {}
    # First, pull URLs from the news sitemap
    status, sitemap, _ = fetch(SITEMAP_URL)
    if status == 200 and sitemap:
        for url, date_str in iter_urls(sitemap):
            if url not in url_to_date:
                url_to_date[url] = date_str
    # Then, supplement with Wayback CDX data for the full range
    CDX_URL = "http://web.archive.org/cdx/search/cdx?url=www.sueddeutsche.de/*&from=20260925&to=20261025&output=json"
    status, cdx_text, _ = fetch(CDX_URL)
    if status == 200 and cdx_text:
        import json
        try:
            rows = json.loads(cdx_text)
        except json.JSONDecodeError:
            rows = []
        # First row is header
        for row in rows[1:]:
            # row format: [urlkey, timestamp, original, ...]
            if len(row) < 3:
                continue
            original = row[2]
            timestamp = row[1]
            try:
                date_obj = datetime.strptime(timestamp[:8], "%Y%m%d")
                date_str = date_obj.strftime(DATE_FMT)
            except Exception:
                continue
            if START <= date_obj <= END:
                if original not in url_to_date:
                    url_to_date[original] = date_str
    # Write TSV output preserving date information
    with open(OUTPUT_TSV, "w", encoding="utf-8") as out:
        for url in sorted(url_to_date):
            out.write(f"{url}\t{url_to_date[url]}\n")

if __name__ == "__main__":
    main()
