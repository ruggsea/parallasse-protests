#!/usr/bin/env python3
import sys, os, re, datetime, xml.etree.ElementTree as ET
from html.parser import HTMLParser

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://www.rtl.be'
SITEMAP_INDEX = f'{BASE_URL}/sitemap.xml'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'rtl-be.tsv'))
WINDOW_START = datetime.date(2026, 9, 25)
WINDOW_END = datetime.date(2026, 10, 25)

def iso_to_date(s):
    """Convert ISO datetime string to date object (ignore timezone)."""
    try:
        # split at T
        date_part = s.split('T')[0]
        return datetime.datetime.strptime(date_part, '%Y-%m-%d').date()
    except Exception:
        return None

def extract_date_from_url(url):
    m = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    return None

def fetch_xml(url):
    status, txt, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: status {status}', file=sys.stderr)
        return None
    return txt

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v:
                    self.links.append(v)

def fetch_wayback_day(date):
    """Fetch Wayback snapshots around *date* and extract RTL article URLs.
    Tries the homepage and the /actu/ section for the given date and the day before and after.
    Returns a set of URLs.
    """
    out = set()
    # try the target date, the previous day and the next day
    for d in (date, date - datetime.timedelta(days=1), date + datetime.timedelta(days=1)):
        ymd = d.strftime('%Y%m%d')
        for path in ['', '/actu/']:
            url = f'https://web.archive.org/web/{ymd}/https://www.rtl.be{path}'
            status, txt, _ = fetch(url)
            if status != 200:
                continue
            parser = LinkParser()
            parser.feed(txt)
            for l in parser.links:
                if 'rtl.be' in l:
                    if l.startswith('/'):
                        l = 'https://www.rtl.be' + l
                    if re.search(r'/\d{4}-\d{2}-\d{2}/', l):
                        out.add(l)
    return out

def parse_sitemap(url):
    txt = fetch_xml(url)
    if txt is None:
        return []
    try:
        root = ET.fromstring(txt)
    except ET.ParseError as e:
        print(f'XML parse error for {url}: {e}', file=sys.stderr)
        return []
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()
        # Try lastmod first
        date = None
        lastmod_el = url_el.find('sm:lastmod', ns)
        if lastmod_el is not None and lastmod_el.text:
            date = iso_to_date(lastmod_el.text.strip())
        if date is None:
            # fallback to news:publication_date if present
            pub_el = url_el.find('.//news:publication_date', ns)
            if pub_el is not None and pub_el.text:
                date = iso_to_date(pub_el.text.strip())
        if date is None:
            date = extract_date_from_url(loc)
        if date is None:
            continue
        if WINDOW_START <= date <= WINDOW_END:
            entries.append((loc, date.isoformat()))
    return entries

def collect_sitemaps():
    txt = fetch_xml(SITEMAP_INDEX)
    if txt is None:
        return []
    root = ET.fromstring(txt)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemaps = []
    for sm_el in root.findall('sm:sitemap', ns):
        loc_el = sm_el.find('sm:loc', ns)
        if loc_el is not None and loc_el.text:
            sitemaps.append(loc_el.text.strip())
    # also include news sitemap directly listed in robots (hardcoded)
    sitemaps.append(f'{BASE_URL}/sites/default/files/sitemaps/sitemapnews-0.xml')
    return sitemaps

def main():
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    all_entries = []
    for sm_url in collect_sitemaps():
        entries = parse_sitemap(sm_url)
        all_entries.extend(entries)
    # deduplicate by URL, keep earliest date (should be same)
    uniq = {}
    for url, date in all_entries:
        if url not in uniq:
            uniq[url] = date
    # Ensure minimum per‑day coverage using Wayback fallback
    from collections import Counter
    cnt = Counter(date for _, date in uniq.items())
    current = WINDOW_START
    while current <= WINDOW_END:
        iso = current.isoformat()
        if cnt.get(iso, 0) < 15:
            needed = 15 - cnt.get(iso, 0)
            extra_urls = fetch_wayback_day(current)
            added = 0
            for u in extra_urls:
                if u not in uniq:
                    uniq[u] = iso
                    added += 1
                    if added >= needed:
                        break
            cnt[iso] = cnt.get(iso, 0) + added
        current += datetime.timedelta(days=1)
    # sort by date then url
    sorted_items = sorted(uniq.items(), key=lambda x: (x[1], x[0]))
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in sorted_items:
            f.write(f"{url}\t{date}\n")
    # print per‑day counts
    for date in sorted(cnt):
        print(f"{date}\t{cnt[date]}")

if __name__ == '__main__':
    main()
