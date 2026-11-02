#!/usr/bin/env python3
"""channelionline.com (Channel i, Bangladesh) article URL lister.

Route: robots.txt is permissive (only /api/, /_next/, /search/, *\/page/ are
disallowed; Crawl-delay 10) and names two sitemaps:
  https://www.channelionline.com/sitemap.xml       -> sitemapindex
  https://www.channelionline.com/news-sitemap.xml  -> Google News sitemap (~last 2 days only)
The index lists 263 <urlset> files under /sitemaps/posts/N.xml (1000 urls each),
ordered OLDEST FIRST (1.xml = 2015-04, 263.xml = newest). Each <url> carries a
<lastmod> in UTC (Z) that equals the news:publication_date of news-sitemap.xml
converted to UTC (checked: newest = 2026-10-27T06:39:52Z vs
2026-10-27T12:39:52+06:00), i.e. lastmod is the PUBLISH time, not edit time.

So: fetch the index, probe a couple of files to learn the direction, then walk
from the newest end backwards until a file lies entirely before the window.
The listed date is the Dhaka-local (+06:00) calendar date of lastmod, which is
the date the site shows on the article page.

Writes data/urls_custom/channelionline-com.tsv : "URL<TAB>YYYY-MM-DD".
"""
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.channelionline.com"
INDEX = BASE + "/sitemap.xml"
OUT = "data/urls_custom/channelionline-com.tsv"

START = date(2026, 9, 25)
END = date(2026, 10, 25)
DHAKA = timezone(timedelta(hours=6))

RE_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
RE_LASTMOD = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S)
RE_URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.S)

MAX_REQUESTS = 40
requests_made = 0


def get(url, tries=3):
    """Fetch through polite_fetch with a couple of retries on 5xx/timeouts."""
    global requests_made
    for i in range(tries):
        if requests_made >= MAX_REQUESTS:
            return 0, ""
        requests_made += 1
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup
            print("  ! %s -> exception %.120r" % (url, exc))
            status, text = 0, ""
        if status == 200 and text:
            return status, text
        if status in (403, 429) or status >= 500 or status == 0:
            continue  # transient / throttling: retry (polite_fetch paces us)
        return status, text or ""
    return status, text or ""


def parse_dt(s):
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", s)
    if not m:
        m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
        if m2:
            y, mo, d = (int(x) for x in m2.groups())
            return None, date(y, mo, d)
        return None
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    if s.endswith("Z"):
        tz = timezone.utc
    else:
        mt = re.search(r"([+-])(\d{2}):?(\d{2})\s*$", s)
        if mt:
            sign = 1 if mt.group(1) == "+" else -1
            tz = timezone(sign * timedelta(hours=int(mt.group(2)), minutes=int(mt.group(3))))
        else:
            tz = timezone.utc
    dt = datetime(y, mo, d, hh, mm, ss, tzinfo=tz)
    return dt, dt.astimezone(DHAKA).date()


def parse_urlset(text):
    """Yield (loc, dhaka_date) for every <url> block that has a lastmod."""
    out = []
    for block in RE_URL_BLOCK.findall(text):
        loc = RE_LOC.search(block)
        if not loc:
            continue
        lm = RE_LASTMOD.search(block)
        if not lm:
            continue
        parsed = parse_dt(lm.group(1))
        if not parsed:
            continue
        out.append((loc.group(1).strip(), parsed[1]))
    return out


def main():
    status, idx = get(INDEX)
    print("index %s -> %s (%d bytes)" % (INDEX, status, len(idx)))
    if status != 200 or not idx:
        print("cannot read sitemap index, aborting")
        write({})
        return

    locs = RE_LOC.findall(idx)
    post_files = []
    for loc in locs:
        m = re.search(r"/sitemaps/posts/(\d+)\.xml$", loc.strip())
        if m:
            post_files.append((int(m.group(1)), loc.strip()))
    if not post_files:
        print("no posts sitemaps in index, aborting")
        write({})
        return
    post_files.sort()
    print("posts sitemaps in index: %d (n=%d..%d)" % (len(post_files), post_files[0][0], post_files[-1][0]))

    numbers = [n for n, _ in post_files]
    urls_by_number = dict(post_files)

    def file_url(n):
        return urls_by_number.get(n) or ("%s/sitemaps/posts/%d.xml" % (BASE, n))

    # Learn the direction: ascending (oldest first) or descending (newest first).
    first_n, last_n = numbers[0], numbers[-1]
    st_a, tx_a = get(file_url(first_n))
    a = parse_urlset(tx_a) if st_a == 200 else []
    st_b, tx_b = get(file_url(last_n))
    b = parse_urlset(tx_b) if st_b == 200 else []
    print("probe %d.xml -> %s %d urls; probe %d.xml -> %s %d urls"
          % (first_n, st_a, len(a), last_n, st_b, len(b)))
    if not a and not b:
        print("cannot read any posts sitemap, aborting")
    date_a = max((d for _, d in a), default=None)
    date_b = max((d for _, d in b), default=None)
    ascending = True
    if date_a and date_b:
        ascending = date_b >= date_a
    print("direction: %s (file %d newest date %s, file %d newest date %s)"
          % ("ascending (newest last)" if ascending else "descending (newest first)",
             first_n, date_a, last_n, date_b))

    found = {}
    for loc, d in a + b:
        if START <= d <= END:
            found.setdefault(loc, d)

    # Walk from the newest end towards older files.
    walk = list(reversed(numbers)) if ascending else list(numbers)
    skipped = {first_n, last_n}
    grace = 2  # keep going this many files past a file that is entirely before the window
    for n in walk:
        if n in skipped:
            continue
        if requests_made >= MAX_REQUESTS:
            print("request budget reached, stopping the walk")
            break
        st, tx = get(file_url(n))
        if st != 200 or not tx:
            print("  %d.xml -> %s, skipped" % (n, st))
            continue
        rows = parse_urlset(tx)
        if not rows:
            print("  %d.xml -> 0 dated urls, skipped" % n)
            continue
        dmin = min(d for _, d in rows)
        dmax = max(d for _, d in rows)
        hits = 0
        for loc, d in rows:
            if START <= d <= END:
                found.setdefault(loc, d)
                hits += 1
        print("  %d.xml %d urls %s..%s -> %d in window" % (n, len(rows), dmin, dmax, hits))
        if dmax < START:
            grace -= 1
            if grace <= 0:
                print("  reached files older than the window, stop")
                break
        if dmin > END:
            continue  # newer than the window, keep walking

    write(found)


def write(found):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(((d.isoformat(), u) for u, d in found.items()))
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for d, u in rows:
            fh.write("%s\t%s\n" % (u, d))
    os.replace(tmp, OUT)
    per_day = {}
    for d, _ in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print("\nwrote %d unique urls to %s (%d requests)" % (len(rows), OUT, requests_made))
    day = START
    while day <= END:
        k = day.isoformat()
        print("  %s: %d" % (k, per_day.get(k, 0)))
        day += timedelta(days=1)
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("  TARGET %s: %d" % (target, per_day.get(target, 0)))


if __name__ == "__main__":
    main()
