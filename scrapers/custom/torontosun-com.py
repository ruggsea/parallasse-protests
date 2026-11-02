#!/usr/bin/env python3
"""torontosun.com (Toronto Sun, Canada) article URL lister for 2026-09-25 .. 2026-10-25.

Route: the site's own HTML news archive, one page per calendar day.
    https://torontosun.com/sitemap/2026-10-10/
Each day page carries an <h1>News archive for October 10, 2026</h1> and a single
    <ul class=sitemap-results-list>
with one <li><a href=/section/sub/slug>Title</a></li> per article published that day,
no pagination (the <footer> follows the list directly).  So the date a URL is listed
under is stated by the site itself, next to the URL.

The year index at https://torontosun.com/sitemap/2026/ links every day as
/sitemap/2026-<month>-<day>/ (month and day NOT zero padded), which is where the URL
shape above comes from.

What does NOT work on this outlet (checked, do not retry):
  * /sitemap.xml              200 but a rolling ~7-day window (~322 URLs), no archive.
  * /sitemap-news.xml         Google-News list, recent only.
  * /sitemap-story.xml        404 (bare and with ?page=/?p=/?amp=).
  * /2026/09/30/ , /2026/10/10/  410 Gone.
  * /category/news/local-news/page/2   404; /news/local-news/page/2 is a SOFT 404
    (200, 300 KB, but the title is "2... | Toronto Sun" and it holds no articles).
  * section pagination is /category/<section>/?from=40, and robots.txt has
    "Disallow: /*?" for "*", so every query-string route (WP REST /wp-json/wp/v2/posts
    with ?after=/?per_page=, ?from= paging, ?outputType=xml) is closed to us.
  * public-api.wordpress.com (WP.com REST v1.1) disallows everything in its robots.txt.
  * Wayback has no captures of this site's sitemaps, so no replay route either.

Listed date = the day archive page the URL sits on (site-stated, verified against the
<h1> on that page); no date is inferred from the URL, which carries none.

Usage: python3 scrapers/custom/torontosun-com.py
Writes: data/urls_custom/torontosun-com.tsv   (URL<TAB>YYYY-MM-DD, no header)
"""
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://torontosun.com"

out_path = os.path.join(os.path.dirname(__file__), '../../data/urls_custom/torontosun-com.tsv')
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# First path segment of things that are not text articles (photo galleries, video,
# the daily pin-up feature, sponsored/uncategorised filler, section and index pages).
SKIP_FIRST = {
    'category', 'sitemap', 'gallery', 'galleries', 'video', 'videos',
    'sunshine-girl', 'sunshine-girls', 'advice', 'sponsored', 'uncategorized',
    'author', 'authors', 'tag', 'tags', 'search', 'newsletters', 'live',
}

UL_RE = re.compile(r'<ul class=sitemap-results-list>(.*?)</ul>', re.S | re.I)
ITEM_RE = re.compile(r'<li>\s*<a\s+href=([^ >]+)[^>]*>(.*?)</a>', re.S | re.I)
H1_RE = re.compile(r'<h1[^>]*>\s*News archive for\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*</h1>', re.I)
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'[ \t\r\f\v]+')


def clean(s):
    s = TAG_RE.sub(' ', s)
    return WS_RE.sub(' ', s).strip()


def is_article(path):
    if not path.startswith('/') or '?' in path or '#' in path:
        return False
    segs = [s for s in path.split('/') if s]
    if len(segs) < 2:
        return False
    if segs[0].lower() in SKIP_FIRST:
        return False
    last = segs[-1]
    if len(last) < 6 or last.isdigit():
        return False
    return True


def list_day(day):
    """Return {url: title} for one calendar day, from the site's day archive page."""
    stamp = f"{day.year}-{day.month}-{day.day}"
    url = f"{BASE}/sitemap/{stamp}/"
    status, text, _ = fetch(url)
    if status != 200 or not text:
        status2, text2, _ = fetch(f"{BASE}/sitemap/{day.year}-{day.month:02d}-{day.day:02d}/")
        if status2 != 200 or not text2:
            print(f"  [{stamp}] HTTP {status}/{status2} - skipped", file=sys.stderr)
            return {}
        status, text = status2, text2
    m = UL_RE.search(text)
    if not m:
        print(f"  [{stamp}] no result list in page ({len(text)} B) - skipped", file=sys.stderr)
        return {}

    # the page states its own date; trust it only if it agrees with what we asked for
    h1 = H1_RE.search(text)
    if h1:
        stated = datetime.date(int(h1.group(3)), MONTHS[h1.group(1).lower()], int(h1.group(2)))
        if stated != day:
            print(f"  [{stamp}] page says {stated} - skipped", file=sys.stderr)
            return {}

    found = {}
    for href, title in ITEM_RE.findall(m.group(1)):
        href = href.strip('\'"')
        if href.startswith('http'):
            if not href.startswith(BASE):
                continue
            href = href[len(BASE):]
        if not is_article(href):
            continue
        href = href.split('#')[0]
        if not href.endswith('/'):
            pass
        found.setdefault(href, clean(title))
    return found


def main():
    t0 = time.time()
    seen = set()
    rows = []
    per_day = {}
    day = START
    while day <= END:
        found = list_day(day)
        kept = 0
        for path in found:
            url = BASE + path
            if url in seen:
                continue
            seen.add(url)
            rows.append((url, day.isoformat()))
            per_day[day.isoformat()] = per_day.get(day.isoformat(), 0) + 1
            kept += 1
        print(f"{day.isoformat()}  {len(found):3d} listed  {kept:3d} new", flush=True)
        day += datetime.timedelta(days=1)

    rows.sort()
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in rows:
            f.write(f"{url}\t{d}\n")

    print(f"\nwrote {out_path}: {len(rows)} unique URLs, {len(per_day)} days, "
          f"{time.time() - t0:.1f}s")
    print("per-day counts:")
    for d in sorted(per_day):
        print(f"  {d}: {per_day[d]}")


if __name__ == '__main__':
    main()
