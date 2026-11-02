#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET

# Add path for polite_fetch module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://cambiocolombia.com'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date(s: str) -> datetime.date:
    # try ISO first
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # fallback: extract YYYY/MM/DD from string
    m = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', s)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError(f'Cannot parse date: {s}')

def fetch_robots_sitemaps():
    url = BASE_URL + '/robots.txt'
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch robots.txt: {status}', file=sys.stderr)
        return []
    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith('sitemap:'):
            s = line.split(':', 1)[1].strip()
            sitemaps.append(s)
    return sitemaps

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: {status}', file=sys.stderr)
        return None
    return text

def iter_urls_from_sitemap(sitemap_url):
    xml_text = fetch_xml(sitemap_url)
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f'XML parse error for {sitemap_url}: {e}', file=sys.stderr)
        return []
    ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    urls = []
    # sitemap index?
    if root.tag.endswith('sitemapindex'):
        for sm in root.findall('ns:sitemap' if ns else 'sitemap', ns):
            loc = sm.find('ns:loc' if ns else 'loc', ns)
            if loc is not None and loc.text:
                urls.extend(iter_urls_from_sitemap(loc.text.strip()))
        return urls
    # regular urlset
    for url_el in root.findall('ns:url' if ns else 'url', ns):
        loc = url_el.find('ns:loc' if ns else 'loc', ns)
        lastmod_el = url_el.find('ns:lastmod' if ns else 'lastmod', ns)
        if loc is None or loc.text is None:
            continue
        url = loc.text.strip()
        date = None
        if lastmod_el is not None and lastmod_el.text:
            try:
                date = parse_date(lastmod_el.text.strip())
            except Exception:
                pass
        # fallback: try to extract date from URL path
        if date is None:
            try:
                date = parse_date(url)
            except Exception:
                pass
        if date is None:
            continue
        if START <= date <= END:
            urls.append((url, date))
    return urls

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'cambiocolombia-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    all_entries = []
    sitemaps = fetch_robots_sitemaps()
    if not sitemaps:
        print('No sitemaps found in robots.txt', file=sys.stderr)
        sys.exit(1)
    for sm in sitemaps:
        all_entries.extend(iter_urls_from_sitemap(sm))
    # deduplicate
    seen = set()
    uniq = []
    for url, date in all_entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, date))
    # sort by date then url
    uniq.sort(key=lambda x: (x[1], x[0]))
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in uniq:
            f.write(f"{url}\t{date.isoformat()}\n")
    # print per‑day counts
    from collections import Counter
    cnt = Counter([d.isoformat() for _, d in uniq])
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")
    print(f"Wrote {len(uniq)} URLs to {out_path}")

if __name__ == '__main__':
    main()
