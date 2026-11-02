#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed {status} for {url}", file=sys.stderr)
        return None
    return text

def parse_sitemap_index(index_url):
    txt = fetch_text(index_url)
    if not txt:
        return []
    root = ET.fromstring(txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [elem.find('ns:loc', ns).text for elem in root.findall('ns:sitemap', ns) if elem.find('ns:loc', ns) is not None]

def parse_urlset(sitemap_url):
    txt = fetch_text(sitemap_url)
    if not txt:
        return []
    root = ET.fromstring(txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        if loc is None:
            continue
        url_text = loc.text.strip()
        # Try news:publication_date first
        pub = url.find('news:news/news:publication_date', ns)
        if pub is not None and pub.text:
            date_text = pub.text.strip()[:10]
        else:
            lastmod = url.find('ns:lastmod', ns)
            date_text = lastmod.text.strip()[:10] if (lastmod is not None and lastmod.text) else None
        entries.append((url_text, date_text))
    return entries

def within_range(date_str):
    if not date_str:
        return False
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        # try ISO datetime
        try:
            d = datetime.datetime.fromisoformat(date_str).date()
        except Exception:
            return False
    return START <= d <= END

def main():
    index_url = 'https://www.detik.com/sitemap.xml'
    sitemap_urls = parse_sitemap_index(index_url)
    print(f"Found {len(sitemap_urls)} sitemap URLs")
    url_date_map = {}
    for sm_url in sitemap_urls:
        entries = parse_urlset(sm_url)
        for url, date_str in entries:
            if within_range(date_str):
                if url not in url_date_map:
                    url_date_map[url] = date_str
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'detik-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(url_date_map.items()):
            f.write(f"{url}\t{d}\n")
    # Print per‑day counts
    counts = {}
    for d in url_date_map.values():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f"{day}\t{counts[day]}")
    print(f"Wrote {len(url_date_map)} URLs to {out_path}")

if __name__ == "__main__":
    main()
