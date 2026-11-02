#!/usr/bin/env python3
"""ertnews.gr (ERT News, Greece) — article URLs published 2026-09-25 .. 2026-10-25.

Route: WordPress date archives expose a per-day RSS feed:
    https://www.ertnews.gr/YYYY/MM/DD/feed/            (35 items per page)
    https://www.ertnews.gr/YYYY/MM/DD/feed/?paged=N    (further pages)
robots.txt allows everything except /livetv/, /advert/, /ertsports/, /ertflix/,
/broadcast/, /video-file/, /wp-json/ — so the WP REST API is closed and is NOT used.
The wp-sitemap index (/sitemap.xml -> wp-sitemap-posts-post-1..144.xml) has <loc>
only, no <lastmod>, and ERT URLs carry no /YYYY/MM/DD/ path, so the sitemap gives
no dates; it was used only to confirm the site is WordPress.
The listed date is the archive day itself (WordPress date archives are cut on
Athens local time), i.e. the day whose feed the article was listed in.
Fallback if a day's feed is empty/unavailable: parse the day's HTML archive page
and its /page/N/ pagination for article links, keeping the same listed date.
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.ertnews.gr"
OUT = "data/urls_custom/ertnews-gr.tsv"
# per-day cache: lets a rerun finish in seconds instead of re-fetching ~500 feeds
CACHE = "data/urls_custom/ertnews-gr.days.json"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

MAX_PAGES = 12          # 12 * 35 = 420 items/day, far above ERT's busiest day
SKIP = re.compile(r"/(livetv|advert|ertsports|ertflix|broadcast|video-file)/")
# links that are site furniture rather than articles
JUNK = re.compile(
    r"(/wp-|/feed/?$|/comments/?$|/page/|/category/|/tag/|/author/|/search|"
    r"xmlrpc\.php|/advert/|/livetv/|/ertsports/|/ertflix/|/broadcast/|/video-file/|"
    r"#|\.(jpg|jpeg|png|gif|css|js|xml|mp3|mp4)$)"
)


def clean(url):
    url = url.strip()
    url = url.split("#")[0]
    if "?" in url:
        url = url.split("?")[0]   # strip tracking/query
    return url


def good(url):
    if not url.startswith(BASE + "/"):
        return False
    path = url[len(BASE):]
    if path.count("/") < 2:      # /section/ only -> a category page
        return False
    if JUNK.search(path) or SKIP.search(path):
        return False
    return True


def day_feed(d):
    """Articles listed in the WordPress date archive for day d (local Athens day)."""
    ymd = d.strftime("%Y/%m/%d")
    found = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE}/{ymd}/feed/" if page == 1 else f"{BASE}/{ymd}/feed/?paged={page}"
        try:
            status, text, _ = fetch(url)
        except Exception as exc:                      # network hiccup: stop this day
            print(f"  {d} feed p{page} error {exc}", file=sys.stderr)
            break
        if status != 200 or not text or "<item>" not in text:
            break
        items = re.findall(r"<item>(.*?)</item>", text, re.S)
        if not items:
            break
        new = 0
        oldest = None
        for it in items:
            m = re.search(r"<link>\s*(.*?)\s*</link>", it)
            pd = re.search(r"<pubDate>\s*(.*?)\s*</pubDate>", it)
            if pd:
                try:
                    dt = parsedate_to_datetime(pd.group(1).strip())
                    if oldest is None or dt < oldest:
                        oldest = dt
                except Exception:
                    pass
            if not m:
                continue
            u = clean(m.group(1))
            if not good(u):
                continue
            if u in found:
                continue
            found.append(u)
            new += 1
        # stop if the page brought nothing new or has drifted well before this day
        if new == 0:
            break
        if oldest is not None and (d - oldest.date()).days > 2:
            break
    return found


def day_html(d):
    """Fallback: parse the day's HTML archive pages (and /page/N/) for article links."""
    ymd = d.strftime("%Y/%m/%d")
    found = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE}/{ymd}/" if page == 1 else f"{BASE}/{ymd}/page/{page}/"
        try:
            status, text, _ = fetch(url)
        except Exception:
            break
        if status != 200 or not text:
            break
        # headline links only: <h2 class="..."><a href="...">
        links = re.findall(r'<h[23][^>]*>\s*<a[^>]+href="([^"]+)"', text)
        if not links:
            links = re.findall(r'<a[^>]+href="(https://www\.ertnews\.gr/[^"]+)"', text)
        new = 0
        for raw in links:
            u = clean(raw)
            if not good(u) or u in found:
                continue
            found.append(u)
            new += 1
        if new == 0:
            break
    return found


def load_cache():
    try:
        with open(CACHE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        pass
    return {}


def save_cache(cache):
    os.makedirs(CACHE.rsplit("/", 1)[0], exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE)


def write_tsv(rows):
    os.makedirs(OUT.rsplit("/", 1)[0], exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for u, day in rows.items():
            f.write(f"{u}\t{day}\n")
    os.replace(tmp, OUT)


def main():
    cache = load_cache()
    rows = {}          # url -> ISO date, first (earliest) day wins
    per_day = {}
    d = START
    while d <= END:
        key = d.isoformat()
        if key in cache and cache[key]:
            arts = cache[key]
        else:
            arts = day_feed(d)
            if len(arts) < 5:
                for u in day_html(d):
                    if u not in arts:
                        arts.append(u)
            if arts:                     # never cache a failed day
                cache[key] = arts
                save_cache(cache)
        kept = []
        for u in arts:
            if u in rows:
                continue
            rows[u] = key
            kept.append(u)
        per_day[key] = len(kept)
        print(f"{key} {len(kept)}", flush=True)
        write_tsv(rows)                  # incremental: a kill still leaves output
        d += timedelta(days=1)

    write_tsv(rows)
    print(f"total {len(rows)} urls -> {OUT}")
    for day in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"check {day}: {per_day.get(day, 0)}")
    thin = [k for k, v in per_day.items() if v == 0]
    if thin:
        print("empty days:", " ".join(thin))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"elapsed {time.time() - t0:.1f}s")
