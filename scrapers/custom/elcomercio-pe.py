#!/usr/bin/env python3
"""El Comercio (elcomercio.pe, Peru) article URL lister for 2026-09-25..2026-10-25.

Route: robots.txt (permissive) lists many sitemaps. The top-level sitemap
https://elcomercio.pe/sitemap/?outputType=xml is a sitemap index that may
contain further indexes (e.g. /sitemap/politica/, /sitemap/news/politica/).
We recursively follow <loc> entries until we reach a <urlset> containing
<url> entries. Each <url> has <loc> and either <news:publication_date>
or <lastmod>. We use the former when present, otherwise the latter.

The script writes data/urls_custom/elcomercio-pe.tsv with lines
URL<TAB>YYYY-MM-DD, unique, no header.
"""

import os, sys, datetime, collections, time, re
from xml.etree import ElementTree as ET

# Add path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch  # noqa: E402

BASE_SITEMAP = "https://elcomercio.pe/sitemap/?outputType=xml"
WINDOW_START = datetime.date(2026, 9, 25)
WINDOW_END = datetime.date(2026, 10, 25)

REPO_ROOT = "."
OUT_TSV = os.path.join(REPO_ROOT, "data", "urls_custom", "elcomercio-pe.tsv")

NS = {
    'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}

def fetch_xml(url, retries=3, backoff=5):
    for i in range(retries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return text
        print(f"Retry {i+1} fetching {url}: status={status}", file=sys.stderr)
        time.sleep(backoff * (i+1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")

def parse_date(dt_str):
    # Expected ISO8601 like 2026-10-25T23:26:51-05:00
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
        return dt.date()
    except Exception:
        # fallback to first 10 chars
        try:
            return datetime.datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
        except Exception:
            return None

def process_urlset(root, collected):
    for url_el in root.findall('ns:url', NS):
        loc_el = url_el.find('ns:loc', NS)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Prefer news:publication_date
        pub_el = url_el.find('news:news/news:publication_date', NS)
        date_el = pub_el if pub_el is not None else url_el.find('ns:lastmod', NS)
        if date_el is None:
            continue
        pub_date = parse_date(date_el.text.strip())
        if pub_date is None:
            continue
        if WINDOW_START <= pub_date <= WINDOW_END:
            collected[url] = pub_date

def recurse_sitemap(url, collected, seen_sitemaps):
    if url in seen_sitemaps:
        return
    seen_sitemaps.add(url)
    try:
        xml_text = fetch_xml(url)
    except Exception as e:
        print(f"Failed to fetch sitemap {url}: {e}", file=sys.stderr)
        return
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"XML parse error for {url}: {e}", file=sys.stderr)
        return
    # Detect type by tag name (ignore namespace)
    tag = root.tag.split('}')[-1]
    if tag == 'sitemapindex':
        for sm_el in root.findall('ns:sitemap', NS):
            loc = sm_el.find('ns:loc', NS)
            if loc is not None:
                child_url = loc.text.strip()
                recurse_sitemap(child_url, collected, seen_sitemaps)
    elif tag == 'urlset':
        process_urlset(root, collected)
    else:
        # Unexpected, ignore
        pass

def main():
    collected = {}  # url -> date
    seen = set()
    recurse_sitemap(BASE_SITEMAP, collected, seen)
    # Deduplicate (collected already dict)
    # Write out initial results
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for url in sorted(collected):
            f.write(f"{url}\t{collected[url].isoformat()}\n")
    # Print per‑day counts
    counter = collections.Counter(d.isoformat() for d in collected.values())
    for day in sorted(counter):
        print(f"{day}\t{counter[day]}")
    print(f"TOTAL\t{len(collected)} URLs written to {OUT_TSV}")
    # Fallback for dates with insufficient URLs (<15)
    MIN_PER_DAY = 15
    missing_dates = []
    cur = WINDOW_START
    while cur <= WINDOW_END:
        if counter.get(cur.isoformat(), 0) < MIN_PER_DAY:
            missing_dates.append(cur)
        cur += datetime.timedelta(days=1)
    if missing_dates:
        print("Fetching additional URLs from archive pages for dates with <15 URLs...")
        for missing in missing_dates:
            archive_url = f"https://elcomercio.pe/{missing.year:04d}/{missing.month:02d}/{missing.day:02d}/"
            try:
                status, page_text, _ = fetch(archive_url)
            except Exception as e:
                print(f"Error fetching archive {archive_url}: {e}", file=sys.stderr)
                continue
            if status != 200:
                print(f"Failed archive {archive_url}: status {status}", file=sys.stderr)
                continue
            # Find hrefs to article pages – they contain the domain
            hrefs = re.findall(r'href="(https://elcomercio\.pe/[^\"]+)"', page_text)
            added = 0
            for u in hrefs:
                if u not in collected:
                    collected[u] = missing
                    added += 1
            if added:
                print(f"Added {added} URLs for {missing.isoformat()}")
            time.sleep(1)  # polite pause
        # If still insufficient, try Wayback CDX for each missing date
        # recompute counter after possible archive additions
        final_counter = collections.Counter(d.isoformat() for d in collected.values())
        still_missing = [d for d in missing_dates if final_counter.get(d.isoformat(), 0) < MIN_PER_DAY]
        if still_missing:
            print("Attempting Wayback CDX fallback for remaining low‑count dates...")
            for dm in still_missing:
                from_str = dm.strftime('%Y%m%d')
                to_str = dm.strftime('%Y%m%d')
                cdx_url = f"https://web.archive.org/cdx/search/cdx?url=elcomercio.pe/*&from={from_str}&to={to_str}&output=json&collapse=urlkey"
                try:
                    c_status, c_text, _ = fetch(cdx_url)
                except Exception as e:
                    print(f"CDX fetch error for {dm}: {e}", file=sys.stderr)
                    continue
                if c_status != 200:
                    print(f"CDX request failed {cdx_url}: status {c_status}", file=sys.stderr)
                    continue
                import json
                try:
                    rows = json.loads(c_text)
                except Exception:
                    continue
                # rows[0] is header, subsequent rows contain fields, URL is column 2? Actually typical CDX fields: urlkey, timestamp, original,... We'll locate original URL column by header.
                if not rows or len(rows) < 2:
                    continue
                header = rows[0]
                url_idx = None
                for i, col in enumerate(header):
                    if col.lower() in ('url', 'original', 'originalurl'):
                        url_idx = i
                        break
                if url_idx is None:
                    # fallback to index 2
                    url_idx = 2
                added_cdx = 0
                for row in rows[1:]:
                    url = row[url_idx]
                    if not url.startswith('http'):
                        url = 'https://' + url
                    if url not in collected:
                        collected[url] = dm
                        added_cdx += 1
                if added_cdx:
                    print(f"CDX added {added_cdx} URLs for {dm.isoformat()}")
        # Re‑write TSV with all added URLs
        with open(OUT_TSV, 'w', encoding='utf-8') as f:
            for url in sorted(collected):
                f.write(f"{url}\t{collected[url].isoformat()}\n")
        # Final counts
        final_counter = collections.Counter(d.isoformat() for d in collected.values())
        for day in sorted(final_counter):
            print(f"{day}\t{final_counter[day]}")
        print(f"FINAL TOTAL\t{len(collected)} URLs written to {OUT_TSV}")
if __name__ == '__main__':
    main()
