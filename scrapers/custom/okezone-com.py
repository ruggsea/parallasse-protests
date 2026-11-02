#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET
# Add path for polite_fetch
sys.path.insert(0, "scrapers")
try:
    from polite_fetch import fetch
except Exception as e:
    print("Failed to import polite_fetch:", e)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date_str(s):
    # Try to parse ISO datetime with timezone
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt.date()
    except Exception:
        pass
    # fallback: first 10 chars YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.date.fromisoformat(m.group(1))
        except Exception:
            pass
    return None

def extract_date(url, lastmod, news_pub):
    # Prefer news publication date if available
    if news_pub:
        d = parse_date_str(news_pub)
        if d:
            return d
    # Try to extract from URL pattern /YYYY/MM/DD/
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
    # Fallback to lastmod
    if lastmod:
        d = parse_date_str(lastmod)
        if d:
            return d
    return None

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed {status} fetching {url}")
        return None
    return text

def get_sitemap_index():
    idx_url = "https://www.okezone.com/sitemap.xml"
    txt = fetch_text(idx_url)
    if not txt:
        return []
    root = ET.fromstring(txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = []
    for loc in root.findall('.//ns:loc', ns):
        locs.append(loc.text.strip())
    return locs

def process_sitemap(surl, collected):
    txt = fetch_text(surl)
    if not txt:
        return
    # Some sitemaps may be gzip-compressed; polite_fetch should decompress automatically.
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        # maybe it's a sitemapindex again, recurse
        try:
            root = ET.fromstring(txt)
        except Exception as e:
            print(f"Parse error {e} for {surl}")
            return
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for url_el in root.findall('.//ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        lastmod_el = url_el.find('ns:lastmod', ns)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None else None
        news_pub_el = url_el.find('.//news:publication_date', ns)
        news_pub = news_pub_el.text.strip() if news_pub_el is not None else None
        d = extract_date(url, lastmod, news_pub)
        if d and START <= d <= END:
            if url not in collected:
                collected[url] = d
    # handle nested sitemapindex
    for sm_el in root.findall('.//ns:sitemap', ns):
        loc = sm_el.find('ns:loc', ns)
        if loc is not None:
            child_url = loc.text.strip()
            process_sitemap(child_url, collected)

def main():
    collected = {}
    sitemap_urls = get_sitemap_index()
    if not sitemap_urls:
        print("No sitemap index found")
        sys.exit(1)
    for s in sitemap_urls:
        process_sitemap(s, collected)
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "okezone-com.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for url, d in sorted(collected.items()):
            f.write(f"{url}\t{d.isoformat()}\n")
    # Print per-day counts
    from collections import Counter
    cnt = Counter([d.isoformat() for d in collected.values()])
    for day in sorted(cnt):
        print(f"{day}: {cnt[day]}")
    print(f"Total URLs: {len(collected)}")

if __name__ == "__main__":
    main()
