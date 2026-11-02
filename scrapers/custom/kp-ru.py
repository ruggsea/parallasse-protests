#!/usr/bin/env python3
import sys, os, gzip, io, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '../../..', 'scrapers')))
# The repository root is three levels up from this file, then scrapers directory
# but the path given may already be correct; adjust safely
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found; ensure it is in scrapers/')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

INDEX_URL = 'https://www.kp.ru/sitemap.xml'

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: HTTP {status}')
    return text

def parse_sitemap_index(text):
    root = ET.fromstring(text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = []
    for sitemap in root.findall('ns:sitemap', ns):
        loc = sitemap.find('ns:loc', ns)
        if loc is not None:
            locs.append(loc.text.strip())
    return locs

def iter_news_sitemaps(sitemap_urls):
    for url in sitemap_urls:
        if 'news_' in url:
            yield url

def fetch_sitemap(url):
    # handle .gz compressed sitemaps
    if url.endswith('.gz'):
        status, data, _ = fetch(url)
        if status != 200:
            raise RuntimeError(f'Failed to fetch gz {url}: HTTP {status}')
        # data is bytes? polite_fetch returns text; assume bytes for gz, but we can decode as latin1 then compress
        # Actually fetch returns text; for gz we need raw bytes. Use fetch with binary? Not supported.
        # Workaround: fetch the url via curl? Not allowed. Instead, skip .gz and prefer .xml versions.
        return None
    else:
        txt = fetch_text(url)
        return txt

def extract_urls(sitemap_xml):
    root = ET.fromstring(sitemap_xml)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    for url_ele in root.findall('ns:url', ns):
        loc = url_ele.find('ns:loc', ns)
        # Prefer news:publication_date if present
        pub = url_ele.find('news:news/news:publication_date', ns)
        if pub is not None and pub.text:
            date_str = pub.text.strip()
        else:
            # fallback to lastmod
            lm = url_ele.find('ns:lastmod', ns)
            if lm is None or not lm.text:
                continue
            date_str = lm.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(date_str)
        except Exception:
            continue
        date = dt.date()
        if START <= date <= END:
            if loc is not None and loc.text:
                url = loc.text.strip()
                yield url, date

def main():
    index_txt = fetch_text(INDEX_URL)
    all_sitemaps = parse_sitemap_index(index_txt)
    # Use all sitemap URLs (both main and news). Prefer XML versions over .gz.
    sitemap_urls = [u for u in all_sitemaps if u.endswith('.xml')]
    collected = {}
    for sm_url in sitemap_urls:
        try:
            xml_text = fetch_sitemap(sm_url)
            if xml_text is None:
                continue
        except Exception as e:
            print(f'Warning: could not fetch {sm_url}: {e}', file=sys.stderr)
            continue
        for url, date in extract_urls(xml_text):
            collected[url] = date
    # Fallback: scrape daily archive pages for dates not covered
    import re
    cur = START
    one_day = datetime.timedelta(days=1)
    while cur <= END:
        archive_url = f'https://www.kp.ru/daily/{cur.year}/{cur.strftime("%m")}/{cur.strftime("%d")}/'
        try:
            page = fetch_text(archive_url)
        except Exception:
            cur += one_day
            continue
        # Find hrefs to /daily/... articles
        for match in re.findall(r'href="(/daily/[^\"]+)"', page):
            full_url = f'https://www.kp.ru{match}'
            # Use the current date as publication date (approx)
            if full_url not in collected:
                collected[full_url] = cur
        cur += one_day
    # Write TSV
    out_path = os.path.abspath(os.path.join(__file__, '../../..', 'data', 'urls_custom', 'kp-ru.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Count per day
    per_day = {}
    for d in collected.values():
        per_day.setdefault(d, 0)
        per_day[d] += 1
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in sorted(collected.items(), key=lambda x: x[1]):
            f.write(f"{url}\t{date.isoformat()}\n")
    # Print stats
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]} URLs")
    print(f"Total URLs written: {len(collected)}")

if __name__ == '__main__':
    main()
