#!/usr/bin/env python3
import os
import sys
import xml.etree.ElementTree as ET
import gzip
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE_URL = "https://www.elmostrador.cl"
OUTPUT_TSV = os.path.abspath("data/urls_custom/elmostrador-cl.tsv")
START_DATE = datetime(2026, 9, 25)
END_DATE = datetime(2026, 10, 25)

def parse_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch sitemap {url}: status {status}", file=sys.stderr)
        return []
    # Handle gzip if needed
    if url.endswith('.gz'):
        import io, gzip
        text = gzip.decompress(text).decode('utf-8')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error for {url}: {e}", file=sys.stderr)
        return []
    ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    entries = []
    for url_el in root.findall('ns:url', ns) if ns else root.findall('url'):
        loc = url_el.find('ns:loc', ns).text if ns else url_el.find('loc').text
        lastmod_el = url_el.find('ns:lastmod', ns) if ns else url_el.find('lastmod')
        lastmod = None
        if lastmod_el is not None and lastmod_el.text:
            try:
                lastmod = datetime.fromisoformat(lastmod_el.text.rstrip('Z'))
            except Exception:
                pass
        # Try news:publication_date if present
        pub_el = url_el.find('.//{http://www.google.com/schemas/sitemap-news/0.9}publication_date')
        if pub_el is not None and pub_el.text:
            try:
                pub_date = datetime.fromisoformat(pub_el.text.rstrip('Z'))
                lastmod = pub_date
            except Exception:
                pass
        # Determine article date: prefer news:publication_date or lastmod, otherwise infer from URL path
        article_date = None
        if lastmod is not None:
            article_date = lastmod.replace(tzinfo=None)
        else:
            # fallback: extract YYYY/MM/DD from URL
            import re
            m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", loc)
            if m:
                try:
                    article_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except Exception:
                    article_date = None
        if article_date is None:
            continue
        if START_DATE <= article_date <= END_DATE:
            entries.append((loc, article_date.date().isoformat()))
    return entries

def main():
    # Discover sitemap index from robots.txt
    status, txt, _ = fetch(f"{BASE_URL}/robots.txt")
    sitemap_urls = []
    if status == 200:
        for line in txt.splitlines():
            if line.lower().startswith('sitemap:'):
                sitemap_urls.append(line.split(':',1)[1].strip())
    else:
        print("Could not fetch robots.txt, proceeding without sitemap index", file=sys.stderr)

    # If we got sitemap URLs, try to walk them (including possible index files)
    all_entries = []
    for sm_url in sitemap_urls:
        if sm_url.endswith('.xml') or sm_url.endswith('.xml.gz'):
            # If this is a sitemap index, we need to fetch children
            if 'index' in sm_url or sm_url.endswith('sitemap-index.xml'):
                # fetch index and recurse
                status, txt, _ = fetch(sm_url)
                if status != 200:
                    continue
                # parse index
                try:
                    root = ET.fromstring(txt)
                except ET.ParseError:
                    continue
                ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
                for sm in (root.findall('ns:sitemap', ns) if ns else root.findall('sitemap')):
                    loc_el = sm.find('ns:loc', ns) if ns else sm.find('loc')
                    if loc_el is not None:
                        child_url = loc_el.text.strip()
                        all_entries.extend(parse_sitemap(child_url))
            else:
                all_entries.extend(parse_sitemap(sm_url))
    # Fallback: try known news sitemap pattern
    if not all_entries:
        # Example: https://www.elmostrador.cl/sitemap-news.xml
        fallback = f"{BASE_URL}/sitemap-news.xml"
        all_entries.extend(parse_sitemap(fallback))

    # Deduplicate
    uniq = {}
    for url, date in all_entries:
        uniq[url] = date

    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for url, date in sorted(uniq.items()):
            f.write(f"{url}\t{date}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(date for _, date in uniq.items())
    for d in sorted(cnt):
        print(f"{d}\t{cnt[d]}")

if __name__ == "__main__":
    main()
