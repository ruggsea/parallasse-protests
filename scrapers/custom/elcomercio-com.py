#!/usr/bin/env python3
import sys, os, datetime, collections

# Insert path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)
import re
import time

SITEMAP_URL = 'https://www.elcomercio.com/sitemap-news.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def parse_date(dt_str):
    # format like 2026-10-25T21:21:35-05:00
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
        return dt.date()
    except Exception:
        return None

def main():
    status, text, _ = fetch(SITEMAP_URL)
    if status != 200:
        print(f'Failed to fetch sitemap, status {status}', file=sys.stderr)
        sys.exit(1)
    # Parse XML with namespaces
    import xml.etree.ElementTree as ET
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(text)
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is None:
            continue
        pub_date = parse_date(pub_el.text.strip())
        if pub_date is None:
            continue
        if START <= pub_date <= END:
            entries.append((url, pub_date))
    # Deduplicate
    seen = set()
    uniq = []
    for url, d in entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, d))
    # Sort by date then url
    uniq.sort(key=lambda x: (x[1], x[0]))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'elcomercio-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in uniq:
            f.write(f"{url}\t{d.isoformat()}\n")
    # Print per-day counts
    counter = collections.Counter([d.isoformat() for _, d in uniq])
    for day in sorted(counter):
        print(f"{day}\t{counter[day]}")
    print(f"Total URLs written: {len(uniq)}")

    # Fallback for dates with insufficient URLs
    MIN_PER_DAY = 15
    dates_needed = []
    cur = START
    while cur <= END:
        cnt = counter.get(cur.isoformat(), 0)
        if cnt < MIN_PER_DAY:
            dates_needed.append(cur)
        cur += datetime.timedelta(days=1)
    if dates_needed:
        print("Fetching additional URLs from archive pages for dates with <15 URLs...")
        for missing_date in dates_needed:
            archive_url = f"https://www.elcomercio.com/{missing_date.year:04d}/{missing_date.month:02d}/{missing_date.day:02d}/"
            status, page_text, _ = fetch(archive_url)
            if status != 200:
                print(f"Failed to fetch archive {archive_url}, status {status}", file=sys.stderr)
                continue
            # Extract hrefs from noscript section (fallback content)
            hrefs = re.findall(r'href="(https://www\.elcomercio\.com/[^"]+)"', page_text)
            added = 0
            for url in hrefs:
                if url not in seen:
                    seen.add(url)
                    uniq.append((url, missing_date))
                    added += 1
            if added:
                print(f"Added {added} URLs for {missing_date.isoformat()}")
            time.sleep(1)  # polite pause
        # Re-sort and write again
        uniq.sort(key=lambda x: (x[1], x[0]))
        with open(out_path, 'w', encoding='utf-8') as f:
            for url, d in uniq:
                f.write(f"{url}\t{d.isoformat()}\n")
        # Reprint final counts
        final_counter = collections.Counter([d.isoformat() for _, d in uniq])
        print("Final per‑day counts after fallback:")
        for day in sorted(final_counter):
            print(f"{day}\t{final_counter[day]}")
        print(f"Total URLs after fallback: {len(uniq)}")

if __name__ == '__main__':
    main()
