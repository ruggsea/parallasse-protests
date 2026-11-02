#!/usr/bin/env python3
"""expansion.mx (Expansión, Mexico) — article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt lists https://expansion.mx/sitemap.xml, a sitemapindex of 8
shards (sitemap1..8.xml).  sitemap1..7 are older archive chunks (0 in-window
URLs except a handful), sitemap8 holds the recent ~48k URLs and covers the whole
window.  Every article URL carries the publication date in its path
/<section>/YYYY/MM/DD/<slug>, which equals the <lastmod> of the sitemap entry and
the page's JSON-LD datePublished (local Mexico date; datePublished is in UTC so
it can be one day later for evening posts).

Union with the Google-News sitemap (/news-sitemap.xml, last ~48h) and the site
feed (/rss) so a shard that briefly lags the newest day is still covered.

All HTTP goes through scrapers/polite_fetch.py.
"""
import datetime
import os
import re
import sys

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "data", "urls_custom", "expansion-mx.tsv")

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
HOSTS = {"expansion.mx", "www.expansion.mx", "expansion.mx."}

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
PATH_DATE_RE = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$)")
PUBC_RE = re.compile(r"<pubDate>\s*([^<]+?)\s*</pubDate>", re.I)
NEWSPUB_RE = re.compile(r"<news:publication_date>\s*([^<]+?)\s*</news:publication_date>", re.I)

MX_TZ = datetime.timezone(datetime.timedelta(hours=-6))


def get(url, note=""):
    """Polite fetch; returns text or '' on any failure."""
    try:
        status, text, _ = fetch(url)
    except Exception as exc:  # network / parse errors must not kill the run
        print("  ! %s %s -> %s" % (url, note, str(exc)[:90]))
        return ""
    if not text:
        print("  ! %s %s -> status %s" % (url, note, status))
        return ""
    return text


def norm(url):
    """Canonical form for de-duplication."""
    url = url.split("#", 1)[0].strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    if url.startswith("https://www.expansion.mx/"):
        url = "https://expansion.mx/" + url[len("https://www.expansion.mx/"):]
    return url


def host_of(url):
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).lower() if m else ""


def date_from_path(url):
    m = PATH_DATE_RE.search(url.split("?", 1)[0])
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def in_window(d):
    return d is not None and START <= d <= END


def utc_string_to_mx_date(s):
    """'2026-10-24T10:05:50-04:00' / 'Tue, 27 Oct 2026 01:43:46 GMT' -> local date."""
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M%z",
                "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(MX_TZ).date()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return None
    return None


def add(rows, url, date):
    if not url or not in_window(date):
        return
    if host_of(url) not in HOSTS:
        return
    url = norm(url)
    if not re.search(r"/(?:19|20)\d\d/\d{1,2}/\d{1,2}/", url):
        return
    if url not in rows:
        rows[url] = date


def main():
    rows = {}

    index = get("https://expansion.mx/sitemap.xml", "index")
    shards = [norm(u) for u in LOC_RE.findall(index) if "sitemap" in u]
    # de-dup while keeping order; ignore any non-sitemap loc
    seen = set()
    shards = [u for u in shards if not (u in seen or seen.add(u))]
    if not shards:
        shards = ["https://expansion.mx/sitemap%d.xml" % n for n in range(1, 9)]
    print("sitemap index: %d shards" % len(shards))

    for shard in shards[:16]:
        text = get(shard, "shard")
        if not text:
            continue
        urls = LOC_RE.findall(text)
        got = 0
        for u in urls:
            d = date_from_path(u)
            if in_window(d):
                before = len(rows)
                add(rows, u, d)
                if len(rows) > before:
                    got += 1
        print("  %-38s %7d locs  %4d new in-window" % (shard.rsplit("/", 1)[-1], len(urls), got))

    # Google-News sitemap (last ~48h) — catches the newest day if a shard lags.
    news = get("https://expansion.mx/news-sitemap.xml", "news-sitemap")
    if news:
        n_before = len(rows)
        for block in re.findall(r"<url>(.*?)</url>", news, re.S):
            lo = LOC_RE.search(block)
            if not lo:
                continue
            u = lo.group(1)
            d = date_from_path(u)
            if not in_window(d):
                pm = NEWSPUB_RE.search(block)
                d = utc_string_to_mx_date(pm.group(1)) if pm else None
            add(rows, u, d)
        print("  news-sitemap.xml                          +%d" % (len(rows) - n_before))

    # Site feed — same idea, a few requests' worth of extra safety.
    feed = get("https://expansion.mx/rss", "rss")
    if feed:
        n_before = len(rows)
        for block in re.findall(r"<item>(.*?)</item>", feed, re.S):
            lm = re.search(r"<link>\s*([^<]+?)\s*</link>", block)
            if not lm:
                continue
            u = lm.group(1)
            d = date_from_path(u)
            if not in_window(d):
                pm = PUBC_RE.search(block)
                d = utc_string_to_mx_date(pm.group(1)) if pm else None
            add(rows, u, d)
        print("  rss                                        +%d" % (len(rows) - n_before))

    # drop OFF-window rows that slipped in through a fallback date
    rows = {u: d for u, d in rows.items() if in_window(d)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for u, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            fh.write("%s\t%s\n" % (u, d.isoformat()))
    os.replace(tmp, OUT)

    per_day = {}
    for d in rows.values():
        per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print("%s  %3d" % (d.isoformat(), per_day[d]))
    print("TOTAL %d unique URLs -> %s" % (len(rows), OUT))
    for probe in (datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)):
        print("check-day %s: %d" % (probe.isoformat(), per_day.get(probe, 0)))


if __name__ == "__main__":
    main()
