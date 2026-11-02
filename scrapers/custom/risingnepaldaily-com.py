#!/usr/bin/env python3
"""The Rising Nepal (risingnepaldaily.com) -- article URLs published 2026-09-25..2026-10-25.

Route: section listings https://risingnepaldaily.com/categories/<slug>?page=N .  Each page has
13 dated entries; the date sits in the entry itself, e.g.

  <li><i class="fas fa-calendar-alt"></i>Sun, 4 October 2026</li>
  ... <h2 class="item-title mb-3"><a href="https://risingnepaldaily.com/news/87381">TITLE</a>

so a pair = first "<W>, <D> <Month> <Y>" then the first /news/<id> link within 700 chars after it.
That is the site's own archive date.  The "latest news" sidebar is dated today (outside the
window) so it drops out, and URLs are de-duplicated anyway.

Dead ends already probed -- do not retry, they cost minutes:
  * /sitemap.xml (advertised in robots.txt) 404s, as do /sitemap_index.xml, /news-sitemap.xml,
    /sitemap-index.xml, /sitemap-news.xml, /sitemap/, /feed.
  * /rss ignores ?page= and ?limit= and always returns the same 10 latest items.  The previous
    version of this script paged that feed and stopped only on an item older than START, which
    never came: it looped until the harness killed it at 200 s.
  * /search and /api/ are robots-disallowed for every crawler.
  * date archives: /archive/YYYY/MM/DD, /archives/..., /news/YYYY/MM/DD,
    /categories/<slug>/YYYY/MM/DD 404; /date/YYYY-MM-DD hangs (no reply in ~31 s).
  * global listings: /all-news, /news/all, /categories/all, /archives, /categories,
    /news?page=N, /latest?page=N 404, and /?page=N is byte-identical (paging ignored).
  * per_page / limit are ignored: page size is fixed at 13 entries.

Speed: listing pages answer in ~1.6-2.6 s, so the crawl runs in a thread pool.  That does not
raise the request rate -- polite_fetch's flock'd per-host limiter (2 req/s here) is the only
gatekeeper.  A wall-clock budget ends the crawl long before the harness limit.
"""
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch  # noqa: E402

HOST = 'https://risingnepaldaily.com'
START = date(2026, 9, 25)
END = date(2026, 10, 25)

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                   'data', 'urls_custom', 'risingnepaldaily-com.tsv'))

# Broad sections first: they carry the day's main stories, so every page of them is dense.
CATEGORIES = [
    'main-news', 'nation', 'politics', 'world', 'sports', 'business', 'society',
    'health', 'science-tech', 'provinces', 'oped', 'opinion', 'editorial',
    'feature', 'life-and-art', 'koshi', 'madhesh', 'bagmati', 'gandaki', 'lumbini',
    'karnali', 'sudurpaschim', 'spectrum', 'detour', 'friday-supplemet',
    'interview', 'photo-news', 'government-special', 'student-corner',
    'gorkhapatra-discourse',
]

# A page of a section listing covers 2-5 days, so ~20 pages reach back to 2026-09-25 even for the
# densest section (main-news walks 2 days per page: p3 = 19-23 Oct, p8 = 9-11 Oct).
MAX_PAGES = 20
MAX_REQUESTS = int(os.environ.get('RN_MAX_REQUESTS', '190'))
MAX_SECONDS = float(os.environ.get('RN_MAX_SECONDS', '95'))
THREADS = 6
TARGETS = (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20))
TARGET_ENOUGH = 20

DATE_RE = re.compile(r'([A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]+ \d{4})')
URL_RE = re.compile(r'href="(https://risingnepaldaily\.com/news/(\d+))"')
WS_RE = re.compile(r'\s+')

state = {'requests': 0, 'errors': 0}
T0 = time.time()


def parse_date(raw):
    for fmt in ('%a, %d %B %Y', '%d %B %Y'):
        try:
            return datetime.strptime(WS_RE.sub(' ', raw).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_listing(html):
    """[(url, date)] for the entries of one listing page, sidebar included (dated today)."""
    out, seen = [], set()
    for m in DATE_RE.finditer(html):
        d = parse_date(m.group(1))
        if d is None:
            continue
        link = URL_RE.search(html, m.end(), m.end() + 700)
        if not link or link.group(1) in seen:
            continue
        seen.add(link.group(1))
        out.append((link.group(1), d))
    return out


def budget_left():
    return (state['requests'] < MAX_REQUESTS
            and time.time() - T0 < MAX_SECONDS)


def fetch_page(task):
    cat, page = task
    # Checked per task, not only per round: a round has one task per live section, so with the
    # rate halved by a 5xx a single round could otherwise overrun the budget by ~30 s.
    if not budget_left():
        return cat, page, 0, []
    status, text, _ = fetch(f'{HOST}/categories/{cat}?page={page}')
    state['requests'] += 1
    if status != 200 or not text:
        state['errors'] += 1
        return cat, page, status, []
    return cat, page, status, parse_listing(text)


def per_day(found):
    counts = {}
    for d in found.values():
        counts[d] = counts.get(d, 0) + 1
    return counts


def main():
    found = {}                      # url -> date, window only

    def elapsed():
        return time.time() - T0

    def in_window(rows):
        for url, d in rows:
            if START <= d <= END:
                found.setdefault(url, d)

    pool = ThreadPoolExecutor(max_workers=THREADS)
    active = [(c, 1) for c in CATEGORIES]
    try:
        while active and budget_left():
            tasks, active = active, []
            # one round = every live category deepened by exactly one page
            for cat, page, status, rows in pool.map(fetch_page, tasks, timeout=300):
                if status != 200 or not rows:
                    continue                       # 404/empty/error: this section is done
                in_window(rows)
                oldest = min(d for _, d in rows)
                if oldest < START or page >= MAX_PAGES:
                    continue                       # window reached bottom of this section
                active.append((cat, page + 1))
            counts = per_day(found)
            print('round done: %d urls, req=%d, %.0fs, targets=%s'
                  % (len(found), state['requests'], elapsed(),
                     {str(d): counts.get(d, 0) for d in TARGETS}), flush=True)
            if all(counts.get(d, 0) >= TARGET_ENOUGH for d in TARGETS):
                print('all target days already well covered; stopping early', flush=True)
                break
    finally:
        pool.shutdown(wait=True)

    if not found:
        raise RuntimeError('no article URLs found -- listing pages did not parse')

    rows = sorted(((u, d) for u, d in found.items()), key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        for url, d in rows:
            fh.write('%s\t%s\n' % (url, d.isoformat()))
    os.replace(tmp, OUT)

    counts = per_day(found)
    print('\nwrote %d unique URLs to %s' % (len(rows), OUT))
    print('requests=%d errors=%d elapsed=%.0fs'
          % (state['requests'], state['errors'], elapsed()))
    day = START
    from datetime import timedelta
    while day <= END:
        print('%s\t%d' % (day.isoformat(), counts.get(day, 0)))
        day += timedelta(days=1)
    print('\ntarget days:')
    for d in TARGETS:
        print('%s\t%d' % (d.isoformat(), counts.get(d, 0)))


if __name__ == '__main__':
    main()
