#!/usr/bin/env python3
"""Scrape article URLs from the Philippine Daily Inquirer (inquirer.net).

Primary source: the public RSS feed (https://www.inquirer.net/feed/). The feed is
paged via the ``?paged=N`` query string and returns about ten items per page,
ordered newest‑first.
If the feed does not provide at least fifteen URLs for a given target date, the
script falls back to the Internet Archive CDX API, which can list historic URLs
for the domain.
All HTTP requests go through ``polite_fetch.fetch`` which respects robots.txt
and rate‑limits.
The collected URLs (unique) are written to ``data/urls_custom/inquirer-net.tsv``
as ``URL<TAB>YYYY-MM-DD`` (no header). A brief per‑day count is printed.
"""

import os
import sys
import time
import datetime
import json
import xml.etree.ElementTree as ET

# Make ``polite_fetch`` importable.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(repo_root, "scrapers"))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
FEED_URL_TEMPLATE = "https://www.inquirer.net/feed/?paged={page}"
OUTPUT_TSV = os.path.abspath(os.path.join(repo_root, "data", "urls_custom", "inquirer-net.tsv"))
os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)

seen_urls = set()
url_to_date = {}
per_day = {}

# ---------------------------------------------------------------------------
# 1. Gather URLs from the RSS feed.
# ---------------------------------------------------------------------------
page = 1
while True:
    feed_url = FEED_URL_TEMPLATE.format(page=page)
    status, text, _ = fetch(feed_url)
    if status != 200:
        sys.stderr.write(f"Feed request failed ({status}): {feed_url}\n")
        break
    if not text:
        break
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        sys.stderr.write(f"XML parse error on page {page}: {e}\n")
        break
    items = root.findall('.//item')
    if not items:
        break
    any_newer = False
    for item in items:
        link_el = item.find('link')
        pub_el = item.find('pubDate')
        if link_el is None or pub_el is None:
            continue
        url = link_el.text.strip()
        pub_raw = pub_el.text.strip()
        try:
            dt = datetime.datetime.strptime(pub_raw, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            continue
        pub_date = dt.date()
        if pub_date > END_DATE:
            # Skip future items, continue scanning.
            continue
        if pub_date < START_DATE:
            # Since the feed is ordered newest→oldest we can stop after this.
            continue
        any_newer = True
        if url not in seen_urls:
            seen_urls.add(url)
            url_to_date[url] = pub_date
            per_day.setdefault(pub_date, 0)
            per_day[pub_date] += 1
    if not any_newer:
        # No items fell inside the window on this page → assume we have passed it.
        break
    page += 1

# ---------------------------------------------------------------------------
# 2. For any date with <15 URLs, use the Wayback CDX fallback.
# ---------------------------------------------------------------------------
def fetch_cdx_for_date(d: datetime.date):
    """Return a set of URLs from the Wayback CDX API for the given date.
    Retries up to 3 times on non‑200 responses.
    """
    from_date = d.strftime('%Y%m%d')
    to_date = d.strftime('%Y%m%d')
    cdx_url = (
        f"https://webcache.googleusercontent.com/cdx/search/cdx?url=www.inquirer.net/*"
        f"&from={from_date}&to={to_date}&output=json&collapse=urlkey"
    )
    attempts = 0
    while attempts < 3:
        status, text, _ = fetch(cdx_url)
        if status == 200 and text:
            try:
                data = json.loads(text)
                # First line is list of field names.
                urls = {row[2] for row in data[1:] if len(row) > 2}
                return urls
            except Exception:
                return set()
        attempts += 1
        time.sleep(2)  # polite pause before retry
    return set()

today = START_DATE
while today <= END_DATE:
    needed = 15 - per_day.get(today, 0)
    if needed > 0:
        cdx_urls = fetch_cdx_for_date(today)
        added = 0
        for u in cdx_urls:
            if u not in seen_urls:
                seen_urls.add(u)
                url_to_date[u] = today
                per_day.setdefault(today, 0)
                per_day[today] += 1
                added += 1
                if per_day[today] >= 15:
                    break
        if added:
            sys.stderr.write(f"CDX added {added} URLs for {today}\n")
    today += datetime.timedelta(days=1)

# ---------------------------------------------------------------------------
# 3. Write TSV.
# ---------------------------------------------------------------------------
with open(OUTPUT_TSV, "w", encoding="utf-8") as out_f:
    for d in sorted(per_day):
        for url in sorted([u for u, dt in url_to_date.items() if dt == d]):
            out_f.write(f"{url}\t{d.isoformat()}\n")

print("Collected URLs per day:")
for d in sorted(per_day):
    print(f"{d}: {per_day[d]} URLs")
