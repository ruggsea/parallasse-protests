#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET

# Add path for polite_fetch (project root scrapers folder is added later)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = 'https://www.cnnbrasil.com.br'
SITEMAP_INDEX = f'{BASE}/sitemap_index.xml'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'cnnbrasil-com-br.tsv'))

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {status} for {url}', file=sys.stderr)
        return None
    return text

def parse_sitemap(url):
    txt = fetch_text(url)
    if not txt:
        return []
    try:
        root = ET.fromstring(txt)
    except ET.ParseError as e:
        print(f'XML parse error {e} for {url}', file=sys.stderr)
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None:
            continue
        link = loc.text.strip()
        date = None
        if lastmod is not None and lastmod.text:
            try:
                dt = datetime.datetime.fromisoformat(lastmod.text.strip())
                date = dt.date()
            except Exception:
                # fallback: take first 10 chars
                try:
                    date = datetime.datetime.strptime(lastmod.text[:10], '%Y-%m-%d').date()
                except Exception:
                    pass
        entries.append((link, date))
    return entries

def main():
    # fetch sitemap index
    index_txt = fetch_text(SITEMAP_INDEX)
    if not index_txt:
        sys.exit(1)
    try:
        idx_root = ET.fromstring(index_txt)
    except ET.ParseError as e:
        print(f'Index XML parse error: {e}', file=sys.stderr)
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [el.find('ns:loc', ns).text.strip() for el in idx_root.findall('ns:sitemap', ns) if el.find('ns:loc', ns) is not None]
    # Process in reverse order (newest first) assuming numeric order
    sitemap_urls.sort(key=lambda u: int(re.search(r'/sitemap/(\d+)\.xml', u).group(1)), reverse=True)
    collected = {}
    for sm_url in sitemap_urls:
        entries = parse_sitemap(sm_url)
        for link, date in entries:
            if date is None:
                continue
            if START <= date <= END:
                collected[link] = date
        # stop early if the smallest date seen so far is before START
        dates = [d for _, d in entries if d]
        if dates and min(dates) < START:
            # we have passed older sitemaps, can break
            break
    # Write TSV
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for link, date in sorted(collected.items()):
            f.write(f"{link}\t{date.isoformat()}\n")
    # print per‑day counts
    from collections import Counter
    cnt = Counter(d.isoformat() for d in collected.values())
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
