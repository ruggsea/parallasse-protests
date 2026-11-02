#!/usr/bin/env python3
"""ilgiorno.it article URLs 2026-09-25..2026-10-25.

Route: the rolling article sitemaps the site advertises in robots.txt:
  /feedservice/sitemap/gio/articles/2026/month/sitemap.xml   (~last 39 days: 2026-09-16..10-23, 4266 urls)
  /feedservice/sitemap/gio/articles/2026/week/sitemap.xml    (~last 8 days: 10-16..10-24, 1018 urls)
  /feedservice/sitemap/generic/gio/2026/day/sitemap.xml      (~last 2 days: 10-24..10-25, 281 urls)
They overlap only in time, not in URLs (checked: 0 URLs appear twice with different dates), so the
three together cover the whole window: ~4400 in-window URLs, 99-167 per day.
Each <url> block is <lastmod> then <loc>; the date written is that lastmod (or news:publication_date
when present). Verified on 128 articles spread over the window: lastmod == JSON-LD datePublished
exactly in 128/128 cases.
Dead ends (probed, all 404/500): per-day or per-month sitemaps with a date in the path
(/articles/2026/09/sitemap.xml = 500, /articles/2026/09/month, /day/09, /month/sitemap09 = 404).
/archivio/ is robots-disallowed, so no archive pages are used.

Filters: URLs with a query string are dropped; the few service pages that are re-dated when the
site edits them (/cosa-fare/ listings: lastmod 2 days after the page date; /meteo/) are dropped.
A final pass re-fetches up to 4 articles per day and drops any whose page date is more than a day
away from the listed date. Wayback CDX is used only for a day that comes out with fewer than 15 URLs.
"""
import datetime as dt
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

OUT = Path("data/urls_custom/ilgiorno-it.tsv")
FIRST, LAST = dt.date(2026, 9, 25), dt.date(2026, 10, 25)
SITEMAPS = [
    "https://www.ilgiorno.it/feedservice/sitemap/index/giorno",
    "https://www.ilgiorno.it/feedservice/sitemap/gio/articles/2026/month/sitemap.xml",
    "https://www.ilgiorno.it/feedservice/sitemap/gio/articles/2026/week/sitemap.xml",
    "https://www.ilgiorno.it/feedservice/sitemap/generic/gio/2026/day/sitemap.xml",
]
SKIP_PREFIX = ("/cosa-fare/", "/meteo/", "/feedservice/", "/image-service/", "/video/")
URL_RE = re.compile(r"^https://www\.ilgiorno\.it(/[^?#\s]+)$")


def get(url):
    status, text, _ = fetch(url, cache=False)
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return status, text or ""


def in_window(d):
    return FIRST.isoformat() <= d <= LAST.isoformat()


def parse_articles(xml):
    """[(url, YYYY-MM-DD)] from a urlset, preferring news:publication_date over lastmod."""
    out = []
    for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", blk)
        if not loc:
            continue
        date = None
        pub = re.search(r"<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>", blk)
        lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", blk)
        for m in (pub, lm):
            if m and re.match(r"^\d{4}-\d{2}-\d{2}", m.group(1)):
                date = m.group(1)[:10]
                break
        if date:
            out.append((loc.group(1), date))
    return out


def harvest(urls, xml):
    for u, d in parse_articles(xml):
        if not in_window(d):
            continue
        m = URL_RE.match(u)
        if not m or m.group(1).startswith(SKIP_PREFIX):
            continue
        prev = urls.get(u)
        if prev is None or d < prev:  # keep the earliest date seen for a URL
            urls[u] = d


def wayback_day(day):
    """CDX fallback: article URLs captured for that day (used only if a day is short)."""
    start = day.replace("-", "")
    end = day.replace("-", "")
    cdx = (
        "https://web.archive.org/cdx/search/cdx?url=www.ilgiorno.it/*&from="
        f"{start}&to={end}&output=json&collapse=urlkey&fl=original,timestamp&filter=statuscode:200"
        "&limit=4000"
    )
    try:
        status, body, _ = fetch(cdx, cache=False)
    except TypeError:
        status, body, _ = fetch(cdx)
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if status != 200 or not body:
        return {}
    found = {}
    for row in re.findall(r'\["([^"]+)","(\d{14})"\]', body)[1:]:
        u = row[0]
        m = URL_RE.match(u)
        if not m or m.group(1).startswith(SKIP_PREFIX):
            continue
        found[u] = day
    return found


def page_date(html):
    for pat in (
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'article:published_time[^>]*?content="([^"]+)"',
        r'<time[^>]+datetime="([^"]+)"',
    ):
        m = re.search(pat, html)
        if m and re.match(r"^\d{4}-\d{2}-\d{2}", m.group(1)):
            return m.group(1)[:10]
    return None


def main():
    urls = {}
    for sm in SITEMAPS:
        status, xml = get(sm)
        before = len(urls)
        if status == 200 and "<loc>" in xml:
            harvest(urls, xml)
        print(f"{status} {sm.split('/sitemap/')[-1]} -> +{len(urls) - before} (total {len(urls)})", flush=True)

    per_day = Counter(urls.values())
    short = [d for d in (FIRST + dt.timedelta(n) for n in range((LAST - FIRST).days + 1)) if per_day[d.isoformat()] < 15]
    for d in short:
        got = wayback_day(d.isoformat())
        added = 0
        for u, dd in got.items():
            if u not in urls:
                urls[u] = dd
                added += 1
        print(f"wayback {d}: +{added} (was {per_day[d.isoformat()]})", flush=True)

    # sample check: up to 4 articles per day must carry a page date within 1 day of the listed date
    by_day = defaultdict(list)
    for u, d in sorted(urls.items()):
        by_day[d].append(u)
    sample = []
    for d in sorted(by_day):
        sample.extend(by_day[d][:4])
    bad = set()

    def check(u):
        d = urls[u]
        status, html = get(u)
        if status != 200:
            return u, None, status
        return u, page_date(html), status

    with ThreadPoolExecutor(4) as ex:
        for u, pdate, status in ex.map(check, sample):
            if pdate is None:
                bad.add(u)
            else:
                delta = abs((dt.date.fromisoformat(urls[u]) - dt.date.fromisoformat(pdate)).days)
                if delta > 1:
                    bad.add(u)
    print(f"sample checked {len(sample)}, dropped {len(bad)}", flush=True)
    for u in bad:
        urls.pop(u, None)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in sorted(urls.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{u}\t{d}\n")

    per_day = Counter(urls.values())
    print(f"wrote {len(urls)} urls to {OUT}", flush=True)
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}", flush=True)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"done in {time.time() - t0:.0f}s", flush=True)
