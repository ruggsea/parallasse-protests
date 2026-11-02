import sys
import os
import json
import time
from datetime import datetime, timedelta

# Ensure sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch import failed')
    sys.exit(1)

BASE_URL = 'https://laverite.mg'
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'laverite-mg.tsv'))

def write_tsv(records):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date_str in records:
            f.write(f"{url}\t{date_str}\n")

def iso_date(dt):
    return dt.strftime('%Y-%m-%d')

records = []
notes = []

# 1. Try WP REST API
rest_url = f"{BASE_URL}/wp-json/wp/v2/posts?per_page=100&_fields=date,link&after={START.isoformat()}&before={END.isoformat()}"
status, text, _ = fetch(rest_url)
notes.append(f'WP REST {rest_url} -> status {status}')
if status == 200 and text:
    try:
        data = json.loads(text)
        for item in data:
            link = item.get('link')
            date = item.get('date')
            if link and date:
                d = date.split('T')[0]
                if START.date() <= datetime.strptime(d, '%Y-%m-%d').date() <= END.date():
                    records.append((link, d))
    except Exception as e:
        notes.append(f'WP REST parse error: {e}')

# 2. Try RSS feed
feed_url = f"{BASE_URL}/feed"
status, text, _ = fetch(feed_url)
notes.append(f'Feed {feed_url} -> status {status}')
if status == 200 and text:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
        for item in root.findall('.//item'):
            link_el = item.find('link')
            pub_el = item.find('pubDate')
            if link_el is not None and pub_el is not None:
                link = link_el.text.strip()
                # parse pubDate like 'Fri, 01 Oct 2026 12:34:56 +0200'
                try:
                    pub_dt = datetime.strptime(pub_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
                    d = pub_dt.strftime('%Y-%m-%d')
                    if START.date() <= pub_dt.date() <= END.date():
                        records.append((link, d))
                except Exception:
                    pass
    except Exception as e:
        notes.append(f'Feed parse error: {e}')

# 3. Try sitemap index (if any)
sitemap_url = f"{BASE_URL}/sitemap.xml"
status, text, _ = fetch(sitemap_url)
notes.append(f'Sitemap {sitemap_url} -> status {status}')
if status == 200 and text:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for sm in root.findall('s:sitemap', ns):
            loc = sm.find('s:loc', ns)
            if loc is not None:
                sm_url = loc.text.strip()
                s_status, s_text, _ = fetch(sm_url)
                notes.append(f'Sub-sitemap {sm_url} -> status {s_status}')
                if s_status == 200 and s_text:
                    try:
                        s_root = ET.fromstring(s_text)
                        for url_el in s_root.findall('s:url', ns):
                            loc_el = url_el.find('s:loc', ns)
                            lastmod_el = url_el.find('s:lastmod', ns)
                            if loc_el is not None and lastmod_el is not None:
                                link = loc_el.text.strip()
                                d = lastmod_el.text[:10]
                                if START.date() <= datetime.strptime(d, '%Y-%m-%d').date() <= END.date():
                                    records.append((link, d))
                    except Exception as e:
                        notes.append(f'Sub-sitemap parse error {sm_url}: {e}')
    except Exception as e:
        notes.append(f'Sitemap parse error: {e}')

# 4. Wayback CDX fallback
cdx_url = f"https://web.archive.org/cdx/search/cdx?url=laverite.mg/*&from=20260925&to=20261025&output=json&collapse=urlkey"
status, text, _ = fetch(cdx_url)
notes.append(f'Wayback CDX {cdx_url} -> status {status}')
if status == 200 and text:
    try:
        rows = json.loads(text)
        for row in rows[1:]:  # first is header
            # row format: [url, timestamp, original, mime, status, digest, length]
            url = row[0]
            ts = row[1]
            d = ts[:8]  # YYYYMMDD
            d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            if START.date() <= datetime.strptime(d_fmt, '%Y-%m-%d').date() <= END.date():
                records.append((url, d_fmt))
    except Exception as e:
        notes.append(f'Wayback parse error: {e}')

# Deduplicate
unique = {}
for url, d in records:
    unique[url] = d
final_records = [(u, d) for u, d in unique.items()]

# Write TSV
write_tsv(final_records)

# Print summary
print('Collected', len(final_records), 'unique URLs')
# Count per day for required dates
for day in ['2026-09-30', '2026-10-10', '2026-10-20']:
    cnt = sum(1 for _, d in final_records if d == day)
    print(day, cnt)

# Write notes for debugging
note_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'grids', 'custom', 'out', 'laverite-mg.json.part'))
with open(note_path, 'w', encoding='utf-8') as f:
    json.dump({
        'script': os.path.relpath(__file__, start=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))),
        'notes': '\n'.join(notes)
    }, f, ensure_ascii=False, indent=2)
