#!/usr/bin/env python3
"""Al-Mada (almadapaper.net) article URL list, 2026-09-25 .. 2026-10-25.

Route: site WordPress RSS feed /feed/?paged=N (10 items/page, walks back in
time). The feed's <content:encoded> holds the FULL article body, so we can
filter to long-form articles without fetching each page: the check re-fetches
sample articles and requires 1500+ chars of body text, and many Al-Mada items
are 1-2 paragraph briefs (~450-950 chars) that fail that. We keep only items
whose feed body (tags stripped) is >= THRESHOLD chars.

Listed date = date-part of the feed <pubDate> (UTC), which matches the date
the page itself displays in its .post-date div (verified on samples: 454983
page '2026-09-30' == feed date 2026-09-30; 456147/456168 same).

Every request goes through polite_fetch (robots, rate limit, logging).
"""
import sys
import os
import re
import html
import datetime
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = 'https://almadapaper.net/feed/'
THRESHOLD = 1600          # min feed-body chars; page extraction matches within ~30 chars
NS_CONTENT = '{http://purl.org/rss/1.0/modules/content/}'

out_dir = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'urls_custom'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'almadapaper-net.tsv')


def body_chars(s):
    s = re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', ' ', s or '')
    s = re.sub(r'(?s)<[^>]+>', ' ', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return len(s)


entries = {}  # url -> (date, max_body_chars)
page = 1
pages_ok = 0
while page <= 250:
    url = BASE if page == 1 else f'{BASE}?paged={page}'
    status, txt, _ = fetch(url)
    if status != 200 or not txt:
        # one retry, then stop (feed order is newest-first, so stopping is safe)
        status, txt, _ = fetch(url)
        if status != 200 or not txt:
            print(f'stop: page {page} status {status}')
            break
    try:
        root = ET.fromstring(txt.encode())
    except Exception as e:
        print(f'stop: page {page} parse error: {e}')
        break
    items = root.findall('./channel/item')
    if not items:
        print(f'stop: page {page} empty')
        break
    pages_ok += 1
    oldest = None
    for it in items:
        link = (it.findtext('link') or '').strip()
        pub = (it.findtext('pubDate') or '').strip()
        if not link or not pub:
            continue
        try:
            d = parsedate_to_datetime(pub).date()
        except Exception:
            continue
        if oldest is None or d < oldest:
            oldest = d
        if not (START <= d <= END):
            continue
        enc = it.find(f'{NS_CONTENT}encoded')
        body = (enc.text or '') if enc is not None else (it.findtext('description') or '')
        n = body_chars(body)
        prev = entries.get(link)
        if prev is None or n > prev[1]:
            entries[link] = (d, n)
    if oldest is not None and oldest < START:
        break
    page += 1

kept = sorted(
    ((u, d) for u, (d, n) in entries.items() if n >= THRESHOLD),
    key=lambda x: (x[1], x[0]),
)

with open(out_path, 'w', encoding='utf-8') as f:
    for u, d in kept:
        f.write(f'{u}\t{d.isoformat()}\n')

cnt_all = Counter(d for _, (d, _) in entries.items())
cnt_kept = Counter(d for _, d in kept)
print(f'pages fetched: {pages_ok}')
print(f'items in window: {len(entries)}  kept (>= {THRESHOLD} chars): {len(kept)}')
print(f'wrote {len(kept)} urls to {out_path}')
for day in sorted(cnt_all):
    print(f'{day.isoformat()}: all={cnt_all[day]} kept={cnt_kept.get(day, 0)}')
