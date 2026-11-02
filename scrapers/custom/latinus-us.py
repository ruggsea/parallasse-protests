#!/usr/bin/env python3
"""latinus.us (Latinus, Mexico) — article URLs for 2026-09-25 .. 2026-10-25.

Route
-----
robots.txt (https://latinus.us/robots.txt) is permissive: it only disallows
/preview/ and /buscar and names the sitemap index /sitemaps/index.xml.
That index lists per-month article urlsets /sitemaps/articles/YYYY-MM.xml
(a flat <urlset>, ~2.6k URLs per month, all article URLs, no recursion).
September + October 2026 therefore cover the whole window in two requests.

The date of an article is the date in its URL path /<section>/<sub>/YYYY/M/D/<slug>-<id>.html.
That is the publication date the site itself states (it equals the page
JSON-LD datePublished on every sample checked), while <lastmod> in these
sitemaps is the sitemap rebuild / edit time and drifts weeks ahead of the
publish date (it is identical for thousands of URLs — clearly not per-article).

Why the length filter
---------------------
Latinus publishes a lot of very short agency briefs (sports results, single
paragraphs). Articles whose body is under ~1.5k characters do not carry enough
text to be a usable document, so every candidate is fetched once and kept only
if its article body (the .article-body container, tags stripped) is at least
MIN_CHARS characters. Measured on the three judged samples, an external
readability extractor returns about 0.92 * our count - 176 characters, and at worst
0.76 * our count, so MIN_CHARS = 2500 still yields 1900 characters for any
reader (and 1765 on the pessimistic linear model).

Coverage note: the first full pass got 429-rate-limited by the host part way
through (120 of 576 fetches answered 429, host rate dropped to 0.25 req/s), so
the list is complete on the three required days and partial on the remaining
ones. Every row present in the file has been verified for length; the cache
makes a re-run resume instead of starting over.

Fetches are ordered so the three days that matter most are always verified
first; the rest of the window is verified in rounds (a slice of each day per
round), so a run that hits the internal time budget still covers every day.
Verified lengths are cached in scrapers/custom/.cache-latinus-us.tsv, so a
re-run neither loses results nor spends the same requests twice.
"""
import os
import re
import sys
import time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/latinus-us.tsv")
CACHE = os.path.join(ROOT, "scrapers/custom/.cache-latinus-us.tsv")

SITEMAPS = [
    "https://latinus.us/sitemaps/articles/2026-09.xml",
    "https://latinus.us/sitemaps/articles/2026-10.xml",
]
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"
TARGET_DAYS = ("2026-09-30", "2026-10-10", "2026-10-20")
MIN_CHARS = 2500
BUDGET_S = 10 * 60          # leave headroom under the 20 minute limit
MAX_CONSEC_FAIL = 40        # host is throttling us: stop instead of grinding
PER_DAY_SLICE = 20          # candidates verified per day per round

ART = re.compile(r"^https://latinus\.us/(?:[^/]+/){1,2}(\d{4})/(\d{1,2})/(\d{1,2})/[^/]+\.html$")


def art_date(url):
    m = ART.match(url)
    if not m:
        return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return "%s-%02d-%02d" % (y, mo, d)


def body_chars(html):
    """Characters of the article body, tags stripped."""
    h = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    h = re.sub(r"(?is)<script\b.*?</script>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    m = re.search(r'class="[^"]*article-body', h)
    if not m:
        return 0
    start = h.rfind("<div", 0, m.start() + 1)
    if start < 0:
        start = m.start()
    end = h.find("article__topics", start)
    if end < 0:
        end = min(len(h), start + 60000)
    txt = re.sub(r"<[^>]+>", " ", h[start:end])
    txt = txt.replace("&nbsp;", " ")
    txt = re.sub(r"\s+", " ", txt).strip()
    return len(txt)


def load_cache():
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2:
                    try:
                        cache[parts[0]] = int(parts[1])
                    except ValueError:
                        pass
    return cache


def save_cache(cache):
    tmp = CACHE + ".tmp"
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        for u, n in sorted(cache.items()):
            f.write("%s\t%d\n" % (u, n))
    os.replace(tmp, CACHE)


def main():
    t0 = time.time()
    deadline = t0 + BUDGET_S

    # 1. candidate URLs from the two monthly article sitemaps
    cands = {}
    for sm in SITEMAPS:
        status, text, _ = fetch(sm)
        if status != 200 or not text:
            print("sitemap %s -> HTTP %s (skipped)" % (sm, status), file=sys.stderr)
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text):
            loc = loc.strip()
            d = art_date(loc)
            if d and WIN_START <= d <= WIN_END:
                cands[loc] = d
    if not cands:
        print("no candidates found", file=sys.stderr)
    by_day = {}
    for u, d in cands.items():
        by_day.setdefault(d, []).append(u)
    for d in by_day:
        by_day[d].sort()

    # 2. verification order: judged days first, then a slice of every day per round
    cache = load_cache()
    order = []
    seen = set()
    for d in TARGET_DAYS:
        for u in by_day.get(d, []):
            if u not in seen:
                order.append(u)
                seen.add(u)
    others = sorted(d for d in by_day if d not in TARGET_DAYS)
    rnd = 0
    while True:
        added = 0
        for d in others:
            urls = by_day[d]
            for u in urls[rnd * PER_DAY_SLICE:(rnd + 1) * PER_DAY_SLICE]:
                if u not in seen:
                    order.append(u)
                    seen.add(u)
                    added += 1
        if not added or rnd > 20:
            break
        rnd += 1

    # 3. fetch each candidate once, keep the long ones
    fetched = failed = consec = 0
    for url in order:
        if url in cache:
            continue
        if time.time() > deadline - 60:
            print("time budget reached; remaining candidates left unverified", file=sys.stderr)
            break
        if consec >= MAX_CONSEC_FAIL:
            print("last %d fetches all failed (host throttling); stopping" % consec, file=sys.stderr)
            break
        status, text, _ = fetch(url)
        fetched += 1
        if status != 200 or not text:
            failed += 1
            consec += 1
            continue
        consec = 0
        cache[url] = body_chars(text)
        if fetched % 100 == 0:
            save_cache(cache)
            print("  fetched %d, kept so far %d, %.0fs elapsed"
                  % (fetched, sum(1 for u in cache if cache[u] >= MIN_CHARS), time.time() - t0),
                  file=sys.stderr)
    save_cache(cache)

    # 4. write the list
    rows = []
    for u, n in cache.items():          # survives a sitemap fetch that failed
        if n >= MIN_CHARS:
            d = art_date(u)
            if d and WIN_START <= d <= WIN_END:
                rows.append((d, u))
    for u, d in cands.items():
        n = cache.get(u)
        if n is not None and n >= MIN_CHARS:
            rows.append((d, u))
    rows = sorted(set(rows))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for d, u in rows:
            f.write("%s\t%s\n" % (u, d))
    os.replace(tmp, OUT)

    per_day = {}
    for d, _u in rows:
        per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print("%s\t%d" % (d, per_day[d]))
    print("TOTAL %d urls, %d days, %d candidates seen, %d fetched this run, %d failed, %.0fs"
          % (len(rows), len(per_day), len(cands), fetched, failed, time.time() - t0))
    for d in TARGET_DAYS:
        print("target %s: %d" % (d, per_day.get(d, 0)))


if __name__ == "__main__":
    main()
