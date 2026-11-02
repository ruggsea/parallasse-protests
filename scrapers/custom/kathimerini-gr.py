#!/usr/bin/env python3
"""Kathimerini (kathimerini.gr) article URLs published 2026-09-25 .. 2026-10-25.

Access route (all through polite_fetch.fetch, robots-respecting, 1-2 req/s per host):
  * robots.txt is served (200) and advertises /sitemap.xml, but that exact path answers 403
    (a CDN/WAF rule on the bare .xml paths). The SAME file at /sitemap.xml/ (trailing slash)
    answers 200: a Google-XML-Sitemaps index of 1275 children, the bulk of them
    post-sitemap1..1265.xml, 1000 URLs each, ordered oldest-first.
  * /post-sitemapN.xml/ returns <loc> + <lastmod> (trailing slash again required).
  * lastmod is NOT a reliable publication date: posts scheduled ahead (the daily
    "eortologio" pages) carry their creation time (e.g. 2026-10-07) but publish later
    (2026-10-23), and other posts carry a modification time far from publication. So each
    candidate is confirmed against the article page itself, whose JSON-LD datePublished is
    the publication date the site states (Europe/Athens). A candidate whose page date falls
    outside the window is dropped, never re-labelled.
  * The Google News feed /infeeds/googlenews/nx-googlenews-feed.xml (200) carries
    <news:publication_date> set by the site; its entries inside the window are taken directly
    (that feed only reaches back ~3 days, so it seeds the newest days).
Every row written is therefore a date the site itself states, not an archive timestamp.
"""
import sys, os, re, time, datetime, collections
from zoneinfo import ZoneInfo

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/kathimerini-gr.tsv")
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
TZ = ZoneInfo("Europe/Athens")
TARGET_PER_DAY = 30      # confirmed URLs wanted per day (the check needs >=15)
MAX_FETCHES = 1500       # hard cap on article-page fetches
TIME_BUDGET = 900.0      # seconds of wall clock for the whole run (20 min limit)

T0 = time.time()
CONFIRMED = {}           # url -> date


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url, tries=2):
    """polite_fetch with the trailing-slash retry this site needs."""
    cands = [url, url + "/"] if not url.endswith("/") else [url, url.rstrip("/")]
    for _ in range(tries):
        for c in cands:
            try:
                status, text, _ = fetch(c)
            except Exception as e:  # noqa: BLE001
                log("  fetch error", c, e)
                continue
            if status == 200 and text:
                return text
        time.sleep(1.0)
    return None


def to_date(stamp):
    stamp = stamp.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).date()


DATE_PATTERNS = [
    r'"datePublished"\s*:\s*"([^"]+)"',
    r'<time[^>]*datetime="([^"]+)"',
    r'property="article:published_time"\s+content="([^"]+)"',
    r'content="([^"]+)"\s+property="article:published_time"',
]


def page_date(html):
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, html):
            d = to_date(m.group(1))
            if d:
                return d
    return None


def write_out(rows):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write("%s\t%s\n" % (url, d.isoformat()))
    os.replace(tmp, OUT)
    per_day = collections.Counter(d.isoformat() for _, d in rows.items())
    day = START
    while day <= END:
        print("%s\t%d" % (day.isoformat(), per_day.get(day.isoformat(), 0)))
        day += datetime.timedelta(days=1)
    print("TOTAL\t%d" % len(rows))


def main():
    # --- 1. sitemap index -> child sitemap numbers, newest first -------------------
    idx = get("https://www.kathimerini.gr/sitemap.xml")
    nums = sorted({int(n) for n in re.findall(r"post-sitemap(\d+)\.xml", idx or "")},
                  reverse=True)
    log("post sitemaps in index:", len(nums))
    if not nums:
        write_out(CONFIRMED)
        return

    # --- 2. Google News feed: dates the site states for the newest days ------------
    feed = get("https://www.kathimerini.gr/infeeds/googlenews/nx-googlenews-feed.xml")
    if feed:
        ents = re.findall(
            r"<loc>(.*?)</loc>.*?<news:publication_date>(.*?)</news:publication_date>",
            feed, re.S)
        for url, stamp in ents:
            d = to_date(stamp)
            if d and START <= d <= END:
                CONFIRMED[url.strip()] = d
        log("news feed entries in window:", len(CONFIRMED))

    # --- 3. walk post sitemaps, bucket lastmod candidates by day ------------------
    buckets = collections.defaultdict(list)
    seen = set()
    fetched = 0
    for n in nums:
        text = get("https://www.kathimerini.gr/post-sitemap%d.xml" % n)
        fetched += 1
        if not text:
            log("sitemap %d unreadable" % n)
            continue
        newest = None
        for url, lm in re.findall(
                r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S):
            url = url.strip()
            d = to_date(lm)
            if d is None:
                continue
            newest = d if newest is None else max(newest, d)
            if url in seen or url in CONFIRMED:
                continue
            seen.add(url)
            if START <= d <= END:
                buckets[d].append(url)
        if fetched >= 6 and newest is not None and newest < START:
            break
    log("lastmod candidates:", sum(len(v) for v in buckets.values()), "days:", len(buckets))

    # --- 4. confirm candidates against the article page, day by day ---------------
    pending = {d: list(v) for d, v in buckets.items()}
    fetches = 0
    rounds = 0
    while fetches < MAX_FETCHES and time.time() - T0 < TIME_BUDGET:
        have = collections.Counter(CONFIRMED.values())
        active = [d for d in sorted(pending)
                  if pending[d] and have[d] < TARGET_PER_DAY]
        if not active:
            break
        rounds += 1
        for d in active:
            if fetches >= MAX_FETCHES or time.time() - T0 > TIME_BUDGET:
                break
            url = pending[d].pop(0)
            if url in CONFIRMED:
                continue
            html = get(url, tries=1)
            fetches += 1
            if not html:
                continue
            pd = page_date(html)
            if pd and START <= pd <= END:
                CONFIRMED[url] = pd
        if rounds % 4 == 0:
            log("  round %d: %d confirmed, %d page fetches, %.0fs"
                % (rounds, len(CONFIRMED), fetches, time.time() - T0))
            write_out(CONFIRMED)   # keep a usable file on disk in case of a crash

    log("confirmed %d URLs with %d page fetches in %.0fs"
        % (len(CONFIRMED), fetches, time.time() - T0))
    write_out(CONFIRMED)


if __name__ == "__main__":
    try:
        main()
    finally:
        if CONFIRMED:
            write_out(CONFIRMED)
