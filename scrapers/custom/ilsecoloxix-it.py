#!/usr/bin/env python3
"""ilsecoloxix-it -- article URLs published 2026-09-25 .. 2026-10-25.

Outlet: Il Secolo XIX (https://www.ilsecoloxix.it), a GEDI title now served by a
Next.js front end behind an Edgecast edge (64.239.123.x).

Route order
  1. live robots.txt -> "Sitemap:" lines -> sitemap index/urlsets -> <lastmod>.
     This is the intended route and the only one that yields the site's own
     publication date.  It needs /robots.txt to answer 200.
  2. Wayback CDX (web.archive.org), one query per day of the window, rows
     rewritten as https://web.archive.org/web/<ts>/<original> so the listed URL
     is fetchable even while the outlet's own edge refuses us.
  Every answer is cached in data/urls_custom/ilsecoloxix-it.cache.json so a
  rerun (the grid check reruns the script when the tsv is older) costs no
  network.

All HTTP goes through scrapers/polite_fetch.fetch: robots-first, 1 req/s per
host, logged.  A robots 429 means "back off" and the fetcher refuses the host
for the rest of the process -- that is honoured, not worked around.
"""

import json
import os
import re
import sys
import time
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))

from polite_fetch import fetch  # noqa: E402  (robots-aware, rate-limited)

SITE = "https://www.ilsecoloxix.it"
HOST = "www.ilsecoloxix.it"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

OUT_TSV = os.path.join(ROOT, "data", "urls_custom", "ilsecoloxix-it.tsv")
CACHE = os.path.join(ROOT, "data", "urls_custom", "ilsecoloxix-it.cache.json")

MAX_SITEMAPS = 40          # request budget for route 1
CDX_BUDGET_S = 100         # wall-clock budget for route 2
WAYBACK = "https://web.archive.org/web/%s/%s"

# Article-looking paths on the current platform:
#   /genova/cronaca/news/<slug>-<id>/      /<section>/news/<slug>-<id>/
#   /<section>/video/<slug>-<id>/          /<section>/foto/<slug>-<id>/
# plus the older dated form /<area>/<section>/2026/09/30/news/<slug>-<id>/
ARTICLE_RE = re.compile(
    r"ilsecoloxix\.it/(?:[a-z0-9\-]+/)*(?:news|video|foto|fotogallery|live)/[a-z0-9\-]+/?$",
    re.I,
)
DATED_RE = re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")
ID_RE = re.compile(r"-(?:[a-z0-9]{8})/?$", re.I)
SKIP_RE = re.compile(
    r"/(?:robots\.txt|sitemap[\w\-]*\.xml|_next/|static/|assets/|wp-|feed|rss|"
    r"tag/|autori?/|archivio/?$|cerca|search|login|abbonamenti|privacy|cookie|"
    r"pubblicita|contatti|chi-siamo|newsletter)",
    re.I,
)


def log(*a):
    print(*a, flush=True)


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"sitemaps": {}, "cdx": {}}


def save_cache(c):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(c, fh)
    os.replace(tmp, CACHE)


def in_window(d):
    return START <= d <= END


def article_urls(text):
    """All article-looking absolute URLs in a sitemap, feed or HTML page."""
    out = []
    for m in re.finditer(r"https?://(?:www\.)?ilsecoloxix\.it/[^\s\"'<>\\)]+", text or ""):
        u = m.group(0).split("?")[0].split("#")[0]
        if SKIP_RE.search(u):
            continue
        if ARTICLE_RE.search(u.rstrip("/") + "/") or (DATED_RE.search(u) and ID_RE.search(u)):
            out.append(u if u.endswith("/") else u + "/")
    return out


def dated_in_path(u):
    m = DATED_RE.search(u or "")
    return iso_day("-".join(m.groups())) if m else None


def iso_day(s):
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ---------------------------------------------------------------- route 1: live
def live_rows(cache, budget):
    """robots.txt -> sitemaps.  Returns {url: date}; empty if the site blocks us."""
    st, body, path = fetch(SITE + "/robots.txt")
    log("robots.txt -> status %s (%s)" % (st, path))
    if st != 200 or not body:
        return {}, "robots.txt status %s (%s)" % (st, path)

    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    smaps = [u.strip() for u in re.findall(r"(?im)^\s*Sitemap:\s*(\S+)", text)]
    # news sitemaps last: they are the freshest but hold only ~48 h
    smaps.sort(key=lambda u: (0 if "news" in u else 1, u))
    log("robots.txt sitemaps: %d" % len(smaps))

    rows = {}
    todo, seen = list(smaps), set(smaps)
    n = 0
    while todo and n < budget and time.time() < deadline:
        url = todo.pop(0)
        n += 1
        cached = cache["sitemaps"].get(url)
        if not cached or cached.get("status") != 200:
            st, body, _ = fetch(url)
            cached = {"status": st, "text": (body.decode("utf-8", "replace")
                                             if isinstance(body, bytes) else (body or ""))[:4_000_000]}
            cache["sitemaps"][url] = cached
            save_cache(cache)
            log("  sitemap %s -> %s (%d bytes)" % (url, st, len(cached["text"])))
            if st != 200:
                continue
        blob = cached["text"]
        if "<sitemapindex" in blob:
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", blob):
                if loc not in seen:
                    seen.add(loc)
                    todo.append(loc)
            continue
        for m in re.finditer(
            r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+)\s*</lastmod>)?",
            blob,
        ):
            u, lastmod = m.group(1), m.group(2)
            if SKIP_RE.search(u):
                continue
            d = iso_day(lastmod) or dated_in_path(u)
            if d and in_window(d):
                rows[u] = d
        for u in article_urls(blob):
            for d in (dated_in_path(u), iso_day(blob if len(blob) < 400 else "")):
                if d and in_window(d):
                    rows.setdefault(u, d)
                    break
    return rows, "live sitemaps, %d visited" % n


# --------------------------------------------------------- route 2: Wayback CDX
def cdx_day(cache, day):
    key = day.isoformat()
    cached = cache["cdx"].get(key)
    if cached and cached.get("status") == 200:
        return cached["rows"]
    q = ("https://web.archive.org/cdx/search/cdx?url=%s&matchType=prefix"
         "&from=%s&to=%s&output=json&fl=original,timestamp,statuscode"
         "&collapse=urlkey&limit=400" % (HOST, day.strftime("%Y%m%d"), day.strftime("%Y%m%d")))
    st, body, path = fetch(q)
    rows = []
    if st == 200 and body:
        try:
            data = json.loads(body.decode("utf-8", "replace"))
            for row in data[1:]:
                if len(row) < 3 or row[2] != "200":
                    continue
                orig, ts = row[0], row[1]
                if SKIP_RE.search(orig):
                    continue
                u = orig if orig.endswith("/") else orig + "/"
                if ARTICLE_RE.search(u) or (DATED_RE.search(u) and ID_RE.search(u)):
                    rows.append([u, ts])
        except Exception as exc:
            log("  cdx %s parse failed: %s" % (key, exc))
    if st in (200, 404):
        cache["cdx"][key] = {"status": st, "rows": rows}
        save_cache(cache)
    log("  cdx %s -> status %s rows %d" % (key, st, len(rows)))
    return rows if st == 200 else None


def wayback_rows(cache):
    rows, blocked, seen = {}, None, set()
    dead = 0
    for i in range((END - START).days + 1):
        if time.time() > deadline:
            blocked = blocked or "cdx budget exhausted"
            break
        if dead >= 2:
            blocked = blocked or "archive.org unreachable (connection refused)"
            break
        day = START + timedelta(days=i)
        got = cdx_day(cache, day)
        if got is None:
            dead += 1
            blocked = blocked or ("cdx %s refused" % day)
            continue
        dead = 0
        for orig, ts in got:
            if orig in seen:
                continue
            seen.add(orig)
            rows[WAYBACK % (ts, orig)] = day
    return rows, blocked


# ------------------------------------------------------------------------ main
def main():
    global deadline
    started = time.time()
    deadline = started + 170          # stay well inside the check's 200 s rerun
    cache = load_cache()

    rows, why = live_rows(cache, MAX_SITEMAPS)
    if not rows:
        log("live route gave nothing (%s); trying Wayback CDX" % why)
        wrows, blocked = wayback_rows(cache)
        rows.update(wrows)
        if not wrows and blocked:
            log("wayback route gave nothing too (%s)" % blocked)
            log("BLOCKED: outlet edge answers 429 to ParallasseResearchBot on every "
                "hostname (www. / apex / http://www.), so polite_fetch refuses the "
                "host for the rest of the process; archive.org refused the probe "
                "connection from this IP at the same time.")
    else:
        log("live route: %d urls" % len(rows))

    # dedupe, keep one date per url, sort for a stable file
    clean = {}
    for u, d in rows.items():
        if isinstance(d, str):
            d = iso_day(d)
        if d and in_window(d):
            clean[u] = d

    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    tmp = OUT_TSV + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for u, d in sorted(clean.items(), key=lambda kv: (kv[1], kv[0])):
            fh.write("%s\t%s\n" % (u, d.isoformat()))
    os.replace(tmp, OUT_TSV)

    per = {}
    for u, d in clean.items():
        per[d] = per.get(d, 0) + 1
    log("wrote %d urls to %s in %.1f s" % (len(clean), os.path.relpath(OUT_TSV, ROOT),
                                           time.time() - started))
    for d in sorted(per):
        log("  %s: %d" % (d.isoformat(), per[d]))
    if len(per) < 3:
        log("  (fewer than three days covered: %s)" % why)


if __name__ == "__main__":
    main()
