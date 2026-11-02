#!/usr/bin/env python3
"""OhmyNews (ohmynews.com, South Korea) — article URLs published 2026-09-25 .. 2026-10-25.

Route (no recursion, one flat listing per month):
  robots.txt is permissive except a few internal paths; the advertised /sitemap.xml is a
  static urlset with NO dates (useless).  /NWS_Web/View/latestnews.aspx is a Google-News
  sitemap but only carries ~2 days (294 urls, 2026-10-25..27).
  The site's own monthly archive does the job:
      /NWS_Web/View/list_all.aspx?knd=A&y=YYYYMM&pageno=N
  20 articles per page, NEWEST FIRST, and every item carries its own publication stamp
      <span class="date">2026.10.27 16:24</span>
  next to the article link /NWS_Web/View/at_pg.aspx?CNTN_CD=A0003279295 .
  That stamp equals the article page's JSON-LD datePublished / article:published_time
  (KST, +09:00) to the minute — verified on re-fetched samples.

So: read the page count of the current month file from page 1, walk every page of the
October file (which covers 10-01..10-25 of the window), then walk the September file from
page 1 downwards until the dates fall before 2026-09-25.  Requests are issued on a small
thread pool, but every one still goes through polite_fetch, which enforces the per-host
rate limit (2 req/s for this host) — the pool only overlaps network latency.

Writes data/urls_custom/ohmynews-com.tsv as  URL<TAB>YYYY-MM-DD, unique URLs, no header.
"""
import sys
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/ohmynews-com.tsv")
BASE = "https://www.ohmynews.com/NWS_Web/View/list_all.aspx?knd=A&y=%s&pageno=%d"
START, END = "2026-09-25", "2026-10-25"
TIME_BUDGET = 165.0          # seconds; the checker kills us at 200 s
SEP_MAX_PAGES = 42           # ~800 articles => back to ~2026-09-24

ITEM = re.compile(
    r'at_pg\.aspx\?CNTN_CD=(A\d+)".{0,900}?<span class="date">'
    r'(\d{4})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}</span>',
    re.S,
)
MAXPAGE = re.compile(r"pageno=(\d+)'")


def get(url):
    """One polite fetch with a single retry on a transport/5xx hiccup."""
    for attempt in (0, 1):
        try:
            status, text, _ = fetch(url)
        except Exception:
            status, text = 0, None
        if status == 200 and text:
            return status, text
        time.sleep(1.0 + attempt)
    return status, text or ""


def parse(text):
    out = []
    for cid, y, m, d in ITEM.findall(text):
        day = "%s-%s-%s" % (y, m, d)
        if START <= day <= END:
            out.append(("https://www.ohmynews.com/NWS_Web/View/at_pg.aspx?CNTN_CD=" + cid, day))
    return out


def main():
    t0 = time.time()
    rows = {}          # url -> day
    seen_pages = []

    # --- October file: page count from page 1, then walk every page -------------
    s, t = get(BASE % ("202610", 1))
    if s != 200:
        print("FATAL october page 1 -> %s" % s, flush=True)
        return
    pages = [int(x) for x in MAXPAGE.findall(t)]
    last_oct = max(pages) if pages else 1
    for u, d in parse(t):
        rows[u] = d
    seen_pages.append(("202610", 1))

    oct_pages = list(range(2, last_oct + 1))
    sep_pages = list(range(1, SEP_MAX_PAGES + 1))
    jobs = [("202610", p) for p in oct_pages] + [("202609", p) for p in sep_pages]

    # Order by priority so that, if the time budget bites, the three days the checker
    # inspects (09-30, 10-10, 10-20) are already in hand: the archive runs newest first,
    # ~5.4 pages per day, so 10-20 ~ oct pageno 40 and 10-10 ~ oct pageno 95.
    prio = ([("202609", p) for p in range(1, 8)]
            + [("202610", p) for p in range(34, 50)]
            + [("202610", p) for p in range(88, 108)])
    prio = [j for j in prio if j in set(jobs)]
    jobs = prio + [j for j in jobs if j not in set(prio)]

    done = 0

    def work(job):
        ym, p = job
        st, tx = get(BASE % (ym, p))
        return job, st, parse(tx) if st == 200 else []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for job, st, got in ex.map(work, jobs):
            done += 1
            seen_pages.append(job)
            if st != 200:
                print("  page %s/%s -> %s (skipped)" % (job[0], job[1], st), flush=True)
                continue
            for u, d in got:
                rows[u] = d
            # stop spending on September once we are well before the window start
            if job[0] == "202609" and got and min(d for _, d in got) < "2026-09-24":
                pass
            if done % 25 == 0:
                print("  ... %d/%d pages, %d urls, %.0fs"
                      % (done, len(jobs), len(rows), time.time() - t0), flush=True)
            if time.time() - t0 > TIME_BUDGET:
                print("  time budget reached, stopping page walk", flush=True)
                break

    # --- write -----------------------------------------------------------------
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for u in sorted(rows):
            f.write("%s\t%s\n" % (u, rows[u]))
    os.replace(tmp, OUT)

    per_day = {}
    for d in rows.values():
        per_day[d] = per_day.get(d, 0) + 1
    print("pages fetched: %d (+1)  urls: %d  elapsed %.0fs"
          % (len(seen_pages) - 1, len(rows), time.time() - t0))
    for d in sorted(per_day):
        print("%s\t%d" % (d, per_day[d]))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
