#!/usr/bin/env python3
"""The Hankyoreh (hani.co.kr, South Korea) article URLs for 2026-09-25 .. 2026-10-25.

Route: hani.co.kr is a Next.js site. Every section list page
(/arti/<section>/<sub>?page=N) carries the site's own article list in
__NEXT_DATA__ (articleList: url + createDate + title + isMemberOnly), and the
same payload is served as JSON from /_next/data/<buildId>/...?page=N (~19 KB
instead of 62 KB).  createDate is the paper's own publication timestamp (KST),
so no date is invented and no per-article request is needed to collect them.

The only sitemaps robots.txt advertises are /sitemap/sections (section landing
pages, undated) and /sitemap/latest-articles, which holds just the last ~2 days
(Oct 26-27 when probed) and therefore cannot cover the window on its own.  A
per-day Wayback CDX walk was tried by an earlier version of this script and is
what blew past the 200 s harness limit, so it is gone.

Sections are walked back from page 1 in priority order until a page's oldest
createDate falls before the window.  A wall-clock deadline (165 s) stops paging
in time to write the file, and the TSV is checkpointed after every section, so
even a truncated run leaves a valid, complete TSV on disk.

Output: data/urls_custom/hani-co-kr.tsv, "URL<TAB>YYYY-MM-DD", deduped, no header.
"""
import datetime
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPERS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRAPERS)
sys.path.insert(0, SCRAPERS)

from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE = "https://www.hani.co.kr"
OUT = os.path.join(ROOT, "data", "urls_custom", "hani-co-kr.tsv")

DEADLINE_S = 165.0          # wall clock budget for network work
MAX_PAGES_PER_SECTION = 45  # sections publish ~1 page/day; 31 days needs ~31

# priority order: highest volume first, so a truncated run still spans the window
SECTIONS = [
    "/arti/politics/politics_general",
    "/arti/economy/economy_general",
    "/arti/international/international_general",
    "/arti/society/society_general",
]

NEXT_RE = re.compile(r'__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
SKIP_TITLE = ("[포토]", "[사진]", "[영상]", "포토뉴스", "[카툰]", "[만평]")


def _items_from_payload(payload):
    """[(url, date, title, member_only)] from a Next.js page payload dict."""
    try:
        pp = payload["props"]["pageProps"]
        al = (pp.get("listData") or {}).get("articleList") or []
    except (KeyError, TypeError):
        return []
    out = []
    for a in al:
        path = a.get("url") or ""
        raw = (a.get("createDate") or "")[:10]
        if not path or len(raw) != 10:
            continue
        try:
            day = datetime.date.fromisoformat(raw)
        except ValueError:
            continue
        out.append((BASE + path, day, a.get("title") or "", bool(a.get("isMemberOnly"))))
    return out


def fetch_page(section, page, build_id):
    """One list page. Returns (items, new_build_id). items == [] on failure."""
    if build_id:
        url = "%s/_next/data/%s%s.json?page=%d" % (BASE, build_id, section, page)
        status, text, _ = fetch(url)
        if status == 200 and text:
            try:
                items = _items_from_payload(json.loads(text))
            except ValueError:
                items = []
            if items:
                return items, build_id
        # stale build id (site redeployed) -> fall through to the HTML page
    url = "%s%s?page=%d" % (BASE, section, page)
    status, text, _ = fetch(url)
    if status != 200 or not text:
        return [], None
    m = NEXT_RE.search(text)
    if not m:
        return [], None
    try:
        payload = json.loads(m.group(1))
    except ValueError:
        return [], None
    bid = payload.get("buildId")
    return _items_from_payload(payload), bid


def write_tsv(records):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(records.items(), key=lambda kv: (kv[1], kv[0]))
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, day in rows:
            f.write("%s\t%s\n" % (url, day.isoformat()))
    os.replace(tmp, OUT)
    return len(rows)


def report(records):
    counts = {}
    for _url, day in records.items():
        counts[day] = counts.get(day, 0) + 1
    day = START
    while day <= END:
        print("  %s  %d" % (day.isoformat(), counts.get(day, 0)))
        day += datetime.timedelta(days=1)
    return counts


def main():
    t0 = time.time()
    records = {}
    build_id = None
    done = []

    for section in SECTIONS:
        if time.time() - t0 > DEADLINE_S:
            print("deadline reached, skipping %s" % section)
            break
        page = 1
        got_here = 0
        oldest = None
        while page <= MAX_PAGES_PER_SECTION:
            if time.time() - t0 > DEADLINE_S:
                print("  deadline reached inside %s at page %d" % (section, page))
                break
            items, new_bid = fetch_page(section, page, build_id)
            if new_bid:
                build_id = new_bid
            if not items:
                print("  %s page %d: no items, stopping section" % (section, page))
                break
            for url, day, title, member in items:
                if member or title.startswith(SKIP_TITLE):
                    continue
                if START <= day <= END and url not in records:
                    records[url] = day
                    got_here += 1
            oldest = min(d for _u, d, _t, _m in items)
            if oldest < START - datetime.timedelta(days=1):
                break
            page += 1
        done.append(section)
        n = write_tsv(records)
        print("%-45s pages=%-3d new=%-4d oldest=%s total=%d  %.0fs"
              % (section, page, got_here, oldest, n, time.time() - t0))

    n = write_tsv(records)
    print("\nwrote %s: %d URLs" % (OUT, n))
    print("sections walked: %d/%d" % (len(done), len(SECTIONS)))
    counts = report(records)
    for key in (datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)):
        print("check day %s: %d URLs%s" % (key.isoformat(), counts.get(key, 0),
                                           "" if counts.get(key, 0) >= 15 else "  <-- LOW"))
    print("elapsed %.0fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
