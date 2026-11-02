#!/usr/bin/env python3
"""The Kathmandu Post (kathmandupost.com) — article URLs published 2026-09-25 .. 2026-10-25.

Route: the site publishes no sitemap and its "Load More" listing endpoint
(/<section>?html=1&pub=<cursor>) only answers JSON to XHR and takes no headers through
polite_fetch, so the live front pages only ever expose the last ~30 articles.
The Wayback Machine, however, captures https://kathmandupost.com/ several times a day,
and the archived homepage carries 70+ article links.  We take one capture per day
(CDX, collapse=timestamp:8) and harvest every /<section>/YYYY/MM/DD/<slug> link from it.
The date is the site's own date in the URL path (validated against JSON-LD datePublished
on sample articles).
"""
import sys, os, re, time, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPERS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRAPERS)
sys.path.insert(0, SCRAPERS)
from polite_fetch import fetch  # noqa: E402

OUT = os.path.join(ROOT, "data", "urls_custom", "kathmandupost-com.tsv")
CACHE = os.path.join(ROOT, "data", "urls_custom", "_wb_kathmandupost")
WIN_START, WIN_END = "2026-09-25", "2026-10-25"

LINK = re.compile(
    r'href="(?:https?://(?:www\.)?kathmandupost\.com)?'
    r'/([a-z0-9][a-z0-9-]*)/(20\d\d)/(\d\d)/(\d\d)/([A-Za-z0-9][A-Za-z0-9%._-]*)"'
)


def cdx_days():
    """Every archived capture of the homepage in the window -> per day (first, last)."""
    q = ("/cdx/search/cdx?url=kathmandupost.com&from=%s&to=%s&output=txt"
         "&fl=timestamp&limit=50000"
         % (WIN_START.replace("-", ""), WIN_END.replace("-", "")))
    for i in range(6):
        scheme = "http" if i % 2 == 0 else "https"
        try:
            status, body, _ = fetch(scheme + "://web.archive.org" + q)
        except Exception:  # noqa: BLE001
            status, body = 0, None
        if status == 200 and body:
            ts = [x for x in body.split() if x.strip().isdigit()]
            if ts:
                per = collections.defaultdict(list)
                for x in ts:
                    per[x[:8]].append(x)
                return [(min(v), max(v)) for _, v in sorted(per.items())]
        print("  cdx attempt %d -> %s" % (i + 1, status), flush=True)
        time.sleep(5)
    return []


def snapshot(stamp):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, stamp + ".html")
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        return open(path, encoding="utf-8", errors="replace").read()
    url = "https://web.archive.org/web/%sid_/https://kathmandupost.com/" % stamp
    status, body, _ = fetch(url)
    if not isinstance(body, str):
        body = (body or b"").decode("utf-8", "replace")
    if status != 200 or len(body) < 50000:
        print("  snapshot %s -> %s (%d bytes)" % (stamp, status, len(body)), flush=True)
        return ""
    text = body
    with open(path, "w") as f:
        f.write(text)
    return text


def add(text, found):
    for sec, y, m, d, slug in LINK.findall(text):
        date = "%s-%s-%s" % (y, m, d)
        if WIN_START <= date <= WIN_END:
            found["https://kathmandupost.com/%s/%s/%s/%s/%s" % (sec, y, m, d, slug)] = date


def main():
    found = {}
    days = cdx_days()
    print("archive days with a homepage capture: %d" % len(days), flush=True)
    for first, last in days:
        # last capture of the day = the day's own stories; first capture of the
        # day still carries the previous evening's front page (first one is
        # usually already on disk from an earlier run).
        for stamp in ((last,) if last == first else (last, first)):
            text = snapshot(stamp)
            if text:
                add(text, found)
        print("  %s -> %d urls total" % (first[:8], len(found)), flush=True)

    # live front page + RSS, to fill days the archive has no capture for
    for url in ("https://kathmandupost.com/", "https://kathmandupost.com/rss"):
        status, body, _ = fetch(url)
        if not isinstance(body, str):
            body = (body or b"").decode("utf-8", "replace")
        if status == 200 and body:
            add(body, found)
            print("  live %s -> %d urls total" % (url, len(found)), flush=True)

    rows = sorted(((u, d) for u, d in found.items()), key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d))

    counts = collections.Counter(d for _, d in rows)
    print("total %d urls, %d days covered" % (len(rows), len(counts)))
    for d in sorted(counts):
        print("  %s %d" % (d, counts[d]))
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("JUDGE %s: %d" % (probe, counts.get(probe, 0)))


if __name__ == "__main__":
    main()
