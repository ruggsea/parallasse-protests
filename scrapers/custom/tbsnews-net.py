#!/usr/bin/env python3
"""The Business Standard (Bangladesh) - tbsnews.net - dated archive route.

What was tried (status codes):
  * https://www.tbsnews.net/robots.txt            200, permissive: only /search/, /admin/,
                                                  /includes/, /user/... disallowed, Crawl-delay: 10.
  * https://www.tbsnews.net/sitemap.xml           404 (robots.txt advertises it, it does not exist)
  * https://tbsnews.net/sitemap.xml               404 (no per-day / per-month sitemaps)
  * https://www.tbsnews.net/googlenews.xml        200, Google News urlset with
                                                  <news:publication_date>, but only ~2 days of items
                                                  (window ended 2026-10-25, today is 2026-10-27) -> useless
                                                  for this window.
  * https://www.tbsnews.net/archive               200 - "Search news by date" page, always today's news
  * /archive/2026-10-10, /archive?date=..., /archive/20261010   all 200 but IGNORE the date parameter
        (they silently render today's news with today's date label - a trap).
  * /sites/all/modules/custom/rsi_news/widgets/archive/archive.js  200 - the datepicker handler:
        document.location = '/archive/' + dateText.replace(/-/g, '/');
    i.e. the real dated archive is /archive/YYYY/MM/DD (slash separated).
  * https://www.tbsnews.net/archive/2026/10/10   200 - label "10 October, 2026", "News (165)",
                                                  148 article links on the single page.
  * https://www.tbsnews.net/archive/2026/10/20   200 - label "20 October, 2026", "News (176)", 155 links.

So: one request per day of the window, the page states its own date in the heading, and the
listed date is that stated day. Requests are spaced 10 s apart because robots.txt says
Crawl-delay: 10 (31 days + overhead ~ 6 min, well under the 20 min budget).
"""
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/urls_custom/tbsnews-net.tsv"

BASE = "https://www.tbsnews.net"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
CRAWL_DELAY = 10.0  # robots.txt: Crawl-delay: 10

# article links look like /<section>/<maybe subsections>/<slug>-<node id>
ART = re.compile(r'href="(/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]*[A-Za-z0-9_-]-\d{6,8})"')
SKIP_SECTION = ("videos", "video", "cartoons", "cartoon", "multimedia", "photo", "gallery", "live")
LABEL = re.compile(r'archive-date">([^<]*)<')
COUNT = re.compile(r"News \((\d+)\)")

_last = [0.0]


def paced_fetch(url):
    """fetch() from polite_fetch, but honouring the site's Crawl-delay: 10."""
    wait = CRAWL_DELAY - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    try:
        return fetch(url)
    finally:
        _last[0] = time.time()


def day_links(day):
    """Return (list of absolute article URLs, stated date string or None)."""
    url = f"{BASE}/archive/{day:%Y/%m/%d}"
    status, text, _ = paced_fetch(url)
    if status != 200 or not text:
        print(f"  ! {day} HTTP {status}", file=sys.stderr)
        return [], None
    m = LABEL.search(text)
    stated = m.group(1).strip() if m else None
    cnt = COUNT.search(text)
    keep, seen = [], set()
    for path in ART.findall(text):
        path = path.split("?")[0].split("#")[0]
        top = path.strip("/").split("/")[0].lower()
        if top in SKIP_SECTION or top == "archive":
            continue
        full = urljoin(BASE, path)
        if full in seen:
            continue
        seen.add(full)
        keep.append(full)
    print(f"  {day}  HTTP 200  stated={stated!r}  declared={cnt.group(1) if cnt else '?'}"
          f"  links={len(keep)}")
    return keep, stated


def main():
    rows = {}  # url -> ISO date
    order = []
    for i in range((END - START).days + 1):
        d = START + timedelta(days=i)
        links, stated = day_links(d)
        if not links:
            continue
        # sanity: the page must state the day we asked for
        if stated:
            norm = lambda s: re.sub(r"^0+(?=\d)", "", s.strip())  # site pads the day: "05 October, 2026"
            want = d.strftime("%d %B, %Y")
            if norm(stated) != norm(want):
                print(f"  ! {d}: page states {stated!r} != {want!r}, skipping this day",
                      file=sys.stderr)
                continue
        iso = d.isoformat()
        for u in links:
            if u in rows:
                continue
            if urlparse(u).netloc not in ("www.tbsnews.net", "tbsnews.net"):
                continue
            rows[u] = iso
            order.append(u)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u in order:
            f.write(f"{u}\t{rows[u]}\n")

    per_day = {}
    for u in order:
        per_day[rows[u]] = per_day.get(rows[u], 0) + 1
    print(f"wrote {len(order)} URLs to {OUT}")
    for d in sorted(per_day):
        print(f"  {d}\t{per_day[d]}")


if __name__ == "__main__":
    main()
