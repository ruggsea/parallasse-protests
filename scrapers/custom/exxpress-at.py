#!/usr/bin/env python3
"""exxpress.at (Austria) article URL collector for 2026-09-25 .. 2026-10-25.

Route (all HTTP via scrapers/polite_fetch.fetch):
  1. https://exxpress.at/robots.txt          -> Sitemap: /sitemap.xml  (User-agent: * -> Allow: /)
  2. /sitemap.xml                            -> sitemapindex with per-month
                                                /sitemap-articles.xml?m=YYYY-MM  (2 requests for the window)
  3. each month urlset: <loc> + <lastmod>; lastmod is the CREATE/EDIT stamp (local time
     written with a Z), so it is a CANDIDATE date only, good enough for selection.
  4. verify each candidate by fetching the article and reading its own publish date
     (meta article:published_time, else JSON-LD datePublished, else <time dateTime>).
     The listed date is that page date. Pages unreadable inside the time budget are dropped,
     so every line in the tsv carries a date the site states on the page.

Parallel workers only fill the 2 req/s the shared polite fetcher allows for this host
(latency ~1.9 s, so serial fetching could not finish ~1300 pages in 20 min).

Output: data/urls_custom/exxpress-at.tsv  (URL<TAB>YYYY-MM-DD, no header, unique)
"""
import os
import re
import sys
import time
import collections
import concurrent.futures as cf

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/exxpress-at.tsv")
START, END = "2026-09-25", "2026-10-25"
PRIORITY_DAYS = ["2026-09-30", "2026-10-10", "2026-10-20"]
BUDGET_S = 15 * 60          # verification budget, whole script stays well under 20 min
WORKERS = 4

MONTHS = []
_y, _m = 2026, 9
while (_y, _m) <= (2026, 10):
    MONTHS.append("%04d-%02d" % (_y, _m))
    _m += 1
    if _m == 13:
        _y, _m = _y + 1, 1

TAG = re.compile(r"<[^>]+>")


def page_text(html):
    h = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", html)
    h = TAG.sub(" ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def page_date(html):
    m = re.search(r'article:published_time"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'<time[^>]+dateTime="([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def month_sitemap(month):
    url = "https://exxpress.at/sitemap-articles.xml?m=%s" % month
    st, txt, _ = fetch(url)
    rows = []
    if st != 200 or not txt:
        print("sitemap %s -> %s" % (month, st))
        return rows
    for block in re.findall(r"<url>(.*?)</url>", txt, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        if loc and lm:
            rows.append((loc.group(1).strip(), lm.group(1).strip()[:10]))
    print("sitemap %s -> %d urls" % (month, len(rows)))
    return rows


def verify(url):
    """Return (url, page publish date YYYY-MM-DD, text length) or None."""
    st, txt, _ = fetch(url, cache=False)
    if st != 200 or not txt:
        return None
    raw = page_date(txt)
    n = len(page_text(txt))
    if not raw or n < 1500:
        return None
    d = raw[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return None
    return (url, d, n)


def main():
    t0 = time.time()
    cands = collections.OrderedDict()
    for month in MONTHS:
        for url, lm in month_sitemap(month):
            # lastmod is create/edit time: allow one day of slack on both sides
            if "2026-09-24" <= lm <= "2026-10-26":
                cands.setdefault(url, lm)

    by_day = collections.defaultdict(list)
    for url, lm in cands.items():
        by_day[lm].append(url)

    # priority: the three check days first (a budget cut then still leaves them complete),
    # then the rest chronologically.
    order = []
    for d in PRIORITY_DAYS:
        order.extend(sorted(by_day.get(d, [])))
    for d in sorted(by_day):
        if d not in PRIORITY_DAYS:
            order.extend(sorted(by_day[d]))
    print("candidates: %d (priority head %d)" % (len(order), sum(len(by_day.get(d, [])) for d in PRIORITY_DAYS)))

    deadline = t0 + BUDGET_S
    results = {}
    done = 0

    def work(u):
        if time.time() > deadline:
            return None
        return verify(u)

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, u): u for u in order}
        for fut in cf.as_completed(futs):
            done += 1
            try:
                res = fut.result()
            except Exception:
                res = None
            if res:
                results[res[0]] = res[1]
            if done % 200 == 0:
                print("  verified %d/%d  elapsed %.0fs  kept %d"
                      % (done, len(order), time.time() - t0, len(results)))

    rows = {}
    for url, d in results.items():
        if START <= d <= END:
            rows[url] = d

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for url, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write("%s\t%s\n" % (url, d))

    per_day = collections.Counter(rows.values())
    print("\nwrote %s : %d unique urls in %.0fs" % (OUT, len(rows), time.time() - t0))
    for d in sorted(per_day):
        print("  %s  %d" % (d, per_day[d]))
    missing = [d for d in PRIORITY_DAYS if per_day.get(d, 0) < 15]
    print("priority days below 15: %s" % (missing or "none"))


if __name__ == "__main__":
    main()
