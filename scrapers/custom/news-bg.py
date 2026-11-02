#!/usr/bin/env python3

import sys
import os
import re
import csv
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    print(f"Failed to import polite_fetch: {e}")
    sys.exit(1)

BASE_URL = "https://news.bg"
ARCHIVE_URL = f"{BASE_URL}/archive"
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def fetch_page(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f"[WARN] {url} returned status {status}")
        return None
    return text

def extract_article_urls(html):
    # find href="https://news.bg/..." links
    pattern = re.compile(r'href\s*=\s*"(https?://news\.bg/[^"#?]+)"')
    urls = set()
    for m in pattern.finditer(html):
        url = m.group(1)
        # ignore obvious sidebar or external shortcuts; keep only news.bg domain
        if url.startswith(BASE_URL):
            urls.add(url.rstrip('/'))
    return urls

def extract_date(text):
    # Look for ISO date in the page (e.g., 2026-09-30) in meta tags or json-ld
    date_pat = re.compile(r'(?P<date>\d{4}-\d{2}-\d{2})')
    for m in date_pat.finditer(text):
        try:
            d = datetime.strptime(m.group('date'), "%Y-%m-%d")
            return d.date()
        except ValueError:
            continue
    return None

def main():
    print("Fetching archive page...")
    archive_html = fetch_page(ARCHIVE_URL)
    if not archive_html:
        sys.exit(1)
    article_urls = extract_article_urls(archive_html)
    print(f"Found {len(article_urls)} candidate URLs on archive page.")

    results = []  # list of (url, date_str)
    per_day_counts = defaultdict(int)

    target_dates = {"2026-09-30", "2026-10-10", "2026-10-20"}
    target_counts = {date: 0 for date in target_dates}
    for idx, url in enumerate(sorted(article_urls)):
        # polite crawl-delay of 10 seconds as per robots.txt
        if idx:
            time.sleep(10)
        page = fetch_page(url)
        if not page:
            continue
        pub_date = extract_date(page)
        if not pub_date:
            continue
        if START.date() <= pub_date <= END.date():
            iso = pub_date.isoformat()
            results.append((url, iso))
            per_day_counts[iso] += 1
            if iso in target_counts:
                target_counts[iso] += 1
        # stop when we have >=15 for each target date
        if all(cnt >= 15 for cnt in target_counts.values()):
            print("Target counts reached for all key dates.")
            break
    # Deduplicate just in case
    unique_results = list(dict.fromkeys(results))

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'news-bg.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, date_str in unique_results:
            writer.writerow([url, date_str])
    print(f"Wrote {len(unique_results)} URLs to {out_path}")
    for date_str in sorted(per_day_counts):
        print(f"{date_str}: {per_day_counts[date_str]} URLs")

if __name__ == "__main__":
    main()
