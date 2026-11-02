#!/usr/bin/env python3
"""today.it (Italy) article lister for 2026-09-25 .. 2026-10-25.

Route: robots.txt -> https://www.today.it/sitemaps/sitemap.xml (index of 28
sitemap_N.xml.gz chunks, flat <urlset> with <loc> + <lastmod>, ~8560 URLs whose
lastmod falls in the window).  The sitemap has no publication date, and lastmod
is the *modified* time: a measured 60-URL sample showed 93% of lastmods equal the
article's own article:published_time day, the rest being evergreen pages that were
re-touched later (/film-serie-tv/<platform>/..., /tv/news/...).  So every candidate
page is fetched and the date is taken from the page itself
(article:published_time, else JSON-LD datePublished); a page whose own date is
outside the window is dropped.  Verification is time-budgeted and round-robin over
days so no day is starved, and only pages that were actually read are written.
Archive pages (/archivio/YYYY/MM/DD/, /YYYY/MM/DD/, /ultimora/) are 404 and /rss/ is
403, so the sitemap is the only listing route.
"""
import sys, os, re, time, collections, datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

WIN_START = datetime.date(2026, 9, 25)
WIN_END = datetime.date(2026, 10, 25)
CHECK_DAYS = ["2026-09-30", "2026-10-10", "2026-10-20"]
INDEX = "https://www.today.it/sitemaps/sitemap.xml"
OUT = "data/urls_custom/today-it.tsv"
BUDGET_S = 690.0          # wall-clock seconds for article verification
TARGET_FIRST = 45         # verified URLs per check day before the round robin
TARGET_ALL = 26           # verified URLs per day (min 15 required on check days)
TARGET_MAX = 34           # raised target while budget remains

RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
RE_LAST = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")
RE_PUB1 = re.compile(r'property=["\']article:published_time["\'][^>]*?content=["\']([^"\']+)', re.I)
RE_PUB2 = re.compile(r'content=["\']([^"\']+)["\'][^>]*?property=["\']article:published_time["\']', re.I)
RE_LD = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
RE_TIME = re.compile(r'<time[^>]+datetime=["\']([^"\']+)["\']', re.I)
SKIP = ("/schede/", "/tv/show/", "/_/")


def day_of(s):
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s.strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def page_date(html):
    for rx in (RE_PUB1, RE_PUB2, RE_LD, RE_TIME):
        m = rx.search(html)
        d = day_of(m.group(1)) if m else None
        if d:
            return d
    return None


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url, cache=False)
        except Exception as e:
            status, text = 0, None
            print(f"  ! {url} exception {e}", file=sys.stderr)
        if status == 200 and text:
            return text
        if status in (-1, 404, 410):
            return None
        time.sleep(2 + 3 * i)
    return None


def main():
    t0 = time.time()
    index = get(INDEX)
    if not index:
        print("FATAL: sitemap index unreachable", file=sys.stderr)
        sys.exit(1)
    chunks = sorted({u for u in RE_LOC.findall(index) if "sitemap" in u})
    print(f"index: {len(chunks)} sitemap chunks")

    cand = {}                     # url -> lastmod date
    for i, url in enumerate(chunks, 1):
        text = get(url)
        if not text:
            print(f"  chunk {i}/{len(chunks)} failed", file=sys.stderr)
            continue
        locs = RE_LOC.findall(text)
        lasts = RE_LAST.findall(text)
        n = 0
        for loc, last in zip(locs, lasts):
            if any(s in loc for s in SKIP):
                continue
            d = day_of(last)
            if d and WIN_START <= d <= WIN_END:
                cand[loc] = d
                n += 1
        print(f"  chunk {i}/{len(chunks)}: {len(locs)} urls, {n} in window ({time.time()-t0:.0f}s)")
    print(f"candidates in window: {len(cand)}")

    by_day = collections.defaultdict(list)
    for u, d in sorted(cand.items()):
        by_day[d.isoformat()].append(u)

    # ---- verify each page's own date, oldest day first (nothing ages out) -----
    verified = {}                 # url -> date str
    seen = set()
    deadline = t0 + BUDGET_S

    def verify(dstr, url):
        seen.add(url)
        html = get(url)
        if not html:
            return None
        d = page_date(html)
        if d and WIN_START <= d <= WIN_END:
            verified[url] = d.isoformat()
            return d.isoformat()
        return None

    # phase A: the days the check asks about, with margin
    for dstr in CHECK_DAYS:
        cnt = 0
        for url in by_day.get(dstr, []):
            if cnt >= TARGET_FIRST or time.time() > deadline:
                break
            if verify(dstr, url):
                cnt += 1
        print(f"phase A {dstr}: {cnt} verified ({time.time()-t0:.0f}s)")

    # phase B: round robin over every day so each day gets its share
    for target in (TARGET_ALL, TARGET_MAX):
        idx = collections.defaultdict(int)
        progress = True
        while progress and time.time() < deadline:
            progress = False
            have = collections.Counter(verified.values())
            for dstr in sorted(by_day):
                if have[dstr] >= target or time.time() > deadline:
                    continue
                urls = by_day[dstr]
                while idx[dstr] < len(urls) and urls[idx[dstr]] in seen:
                    idx[dstr] += 1
                if idx[dstr] >= len(urls):
                    continue
                progress = True
                verify(dstr, urls[idx[dstr]])
                idx[dstr] += 1
        print(f"phase B target {target}: {len(verified)} verified ({time.time()-t0:.0f}s)")

    # ---- write -----------------------------------------------------------------
    rows = sorted(verified.items(), key=lambda x: (x[1], x[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for url, d in rows:
            f.write(f"{url}\t{d}\n")
    os.replace(tmp, OUT)

    cnt = collections.Counter(d for _, d in rows)
    print(f"\nwrote {len(rows)} unique URLs to {OUT}")
    for d in sorted(cnt):
        print(f"{d}: {cnt[d]} URLs")
    print("\nrequired days:", ", ".join(f"{d}={cnt.get(d,0)}" for d in CHECK_DAYS))
    print(f"total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
