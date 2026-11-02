#!/usr/bin/env python3

import sys
import os
import csv
import time
import json
from datetime import datetime, timedelta

# Ensure polite_fetch is importable (project relative path)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

DOMAIN = 'smni.com'
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'smni-com.tsv'))

def daterange(start, end):
    for n in range(int((end - start).days) + 1):
        yield start + timedelta(days=n)

# Collect URLs by date
urls_by_date = {d.strftime('%Y-%m-%d'): set() for d in daterange(START, END)}

def add_url(url, date_str):
    if date_str in urls_by_date:
        urls_by_date[date_str].add(url)

# 1. Try WordPress REST API (if site uses WP). This is a guess; many sites block it.
def fetch_wp_posts():
    per_page = 100
    page = 1
    while True:
        api_url = f'https://{DOMAIN}/wp-json/wp/v2/posts?per_page={per_page}&page={page}&after={START.isoformat()}Z&before={END.isoformat()}Z'
        status, text, _ = fetch(api_url)
        if status != 200:
            # Assuming blocked or not WP
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return
        if not data:
            break
        for post in data:
            link = post.get('link') or post.get('guid', {}).get('rendered')
            date_gmt = post.get('date_gmt') or post.get('date')
            if link and date_gmt:
                try:
                    dt = datetime.strptime(date_gmt, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    continue
                date_str = dt.strftime('%Y-%m-%d')
                add_url(link, date_str)
        if len(data) < per_page:
            break
        page += 1
        time.sleep(1)  # be polite

# 2. Wayback CDX fallback
def fetch_wayback_cdx():
    cdx_url = (
        f'http://web.archive.org/cdx/search/cdx?url={DOMAIN}/*&from=20260925&to=20261025'
        '&output=json&collapse=urlkey'
    )
    status, text, _ = fetch(cdx_url)
    if status != 200:
        return
    try:
        rows = json.loads(text)
    except json.JSONDecodeError:
        return
    if not rows or len(rows) < 2:
        return
    header = rows[0]
    # typical fields: urlkey, timestamp, original, mimetype, statuscode, digest, length
    # We'll use 'original' and 'timestamp'
    idx_original = header.index('original') if 'original' in header else 2
    idx_timestamp = header.index('timestamp') if 'timestamp' in header else 1
    for row in rows[1:]:
        try:
            url = row[idx_original]
            ts = row[idx_timestamp]
            dt = datetime.strptime(ts, '%Y%m%d%H%M%S')
            date_str = dt.strftime('%Y-%m-%d')
            add_url(url, date_str)
        except Exception:
            continue

def write_output():
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for date_str in sorted(urls_by_date.keys()):
            for url in sorted(urls_by_date[date_str]):
                writer.writerow([url, date_str])

def report_counts():
    for date_str in sorted(urls_by_date.keys()):
        count = len(urls_by_date[date_str])
        if count:
            print(f'{date_str}: {count} URLs')

def main():
    fetch_wp_posts()
    fetch_wayback_cdx()
    write_output()
    report_counts()

if __name__ == '__main__':
    main()
    # Update status JSON with notes about the approach
    status_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'grids', 'custom', 'out', 'smni-com.json.part'))
    try:
        with open(status_path, 'w', encoding='utf-8') as jf:
            json.dump({
                'script': os.path.relpath(__file__, start=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))),
                'notes': 'Collected URLs via WP REST API (if available) and Wayback CDX fallback. Deduplicated by date.'
            }, jf)
    except Exception as e:
        print(f'Failed to write status JSON: {e}')
