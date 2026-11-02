#!/usr/bin/env python3
"""tanea.gr (Ta Nea, Greece) - article URLs published 2026-09-25 .. 2026-10-25.

Route: the site is WordPress and its REST API is open and unauthenticated:
    GET /wp-json/wp/v2/posts?per_page=30&page=N
        &after=YYYY-MM-DDT00:00:00&before=YYYY-MM-DDT00:00:00
        &orderby=date&order=desc&_fields=id,date,link
`date` is the site's own local publication timestamp (Europe/Athens), and `link`
is the permalink, which also carries /YYYY/MM/DD/. Pagination stops on an empty
array or an HTTP 400 ("rest_post_invalid_page_number").

per_page is capped by the site's WAF at 30 (31..100 answer HTTP 403), so the
window is walked one local day at a time with page=1.. until a short page.

Fallback (only if a day comes back empty): the news sitemap advertised in
robots.txt, https://www.tanea.gr/wp-content/uploads/json/sitemap-news.xml,
which carries <news:publication_date> but only ever holds the last ~100 posts.

All HTTP goes through polite_fetch (robots.txt first, per-host rate limit, log).
Output: data/urls_custom/tanea-gr.tsv   URL<TAB>YYYY-MM-DD
"""
import html as html_mod
import json
import os
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/tanea-gr.tsv")

START = date(2026, 9, 25)
END = date(2026, 10, 25)

API = "https://www.tanea.gr/wp-json/wp/v2/posts"
NEWS_SITEMAP = "https://www.tanea.gr/wp-content/uploads/json/sitemap-news.xml"
PER_PAGE = 30

LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
NEWS_DATE = re.compile(r"<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>")
LASTMOD = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")

# Posts whose own body text is under this many characters are stubs the site
# itself publishes as one-line briefs, video notes or photo captions; they are
# not article pages and carry no readable text on the rendered page either.
MIN_BODY = 700

found = {}          # url -> YYYY-MM-DD
requests_made = 0

def body_len(item):
    """Characters of plain text in the post's own rendered content."""
    c = (item.get("content") or {}).get("rendered", "") or ""
    c = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", c)
    return len(re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"(?s)<[^>]+>", " ", c))).strip())


def get(url, tries=3):
    """polite_fetch with a slow retry on 403/429/5xx (WAF hiccups, not robots)."""
    global requests_made
    for attempt in range(tries):
        status, text, _robots = fetch(url)
        requests_made += 1
        if status == 200 and text:
            return status, text
        if status in (400, 404):
            return status, text or ""
        time.sleep(5 * (attempt + 1))
    return status, text or ""


def add(url, day):
    url = url.strip()
    if not url or day is None:
        return
    if not (START <= day <= END):
        return
    if url in found:
        return
    found[url] = day.isoformat()


def day_from_iso(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def rest_day(d):
    """All posts whose site-local publication date is d, via the REST API."""
    after = "%sT00:00:00" % d.isoformat()
    before = "%sT00:00:00" % (d + timedelta(days=1)).isoformat()
    got = 0
    page = 1
    while page <= 40:
        url = ("%s?per_page=%d&page=%d&after=%s&before=%s"
               "&orderby=date&order=desc&_fields=id,date,link,content"
               % (API, PER_PAGE, page, after, before))
        status, text = get(url)
        if status != 200:
            # 400 = past the last page; anything else ends this day.
            break
        try:
            items = json.loads(text)
        except ValueError:
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            link = it.get("link")
            dday = day_from_iso(it.get("date"))
            if not link or not dday:
                continue
            if body_len(it) >= MIN_BODY:
                add(link, dday)
                if dday == d:
                    got += 1
        if len(items) < PER_PAGE:
            break
        page += 1
    return got


def rest_whole_window():
    """Belt and braces: one paged sweep over the whole window, so a post whose
    local date sits on a boundary is not missed by the per-day before/after."""
    after = "%sT00:00:00" % START.isoformat()
    before = "%sT00:00:00" % (END + timedelta(days=1)).isoformat()
    page = 1
    while page <= 200:
        url = ("%s?per_page=%d&page=%d&after=%s&before=%s"
               "&orderby=date&order=desc&_fields=id,date,link,content"
               % (API, PER_PAGE, page, after, before))
        status, text = get(url)
        if status != 200:
            break
        try:
            items = json.loads(text)
        except ValueError:
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            if it.get("link") and body_len(it) >= MIN_BODY:
                add(it["link"], day_from_iso(it.get("date")))
        if len(items) < PER_PAGE:
            break
        page += 1


def news_sitemap():
    status, text = get(NEWS_SITEMAP)
    if status != 200:
        return 0
    n = 0
    for block in re.findall(r"<url>(.*?)</url>", text, re.S):
        m = LOC.search(block)
        if not m:
            continue
        url = m.group(1)
        dm = NEWS_DATE.search(block) or LASTMOD.search(block)
        if not dm:
            continue
        before = len(found)
        add(url, day_from_iso(dm.group(1)))
        if len(found) > before:
            n += 1
    return n


def main():
    t0 = time.time()
    per_day = {}
    d = START
    while d <= END:
        # Only days whose failure would matter get the fallback treatment.
        before = len(found)
        n = rest_day(d)
        per_day[d] = len(found) - before
        print("  %s  %3d urls (api said %d)" % (d.isoformat(), per_day[d], n), flush=True)
        d += timedelta(days=1)

    total_day_chunks = len(found)
    print("per-day sweep: %d urls in %.1fs (%d requests)"
          % (total_day_chunks, time.time() - t0, requests_made), flush=True)

    # Fill any thin day with the whole-window sweep, then the news sitemap.
    thin = [dd for dd, c in per_day.items() if c < 15]
    if thin:
        print("days under 15 (%s) -> whole-window sweep" %
              ", ".join(x.isoformat() for x in thin), flush=True)
        rest_whole_window()
    news_sitemap()

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, day in rows:
            f.write("%s\t%s\n" % (url, day))
    os.replace(tmp, OUT)

    counts = {}
    for _url, day in rows:
        counts[day] = counts.get(day, 0) + 1
    print("\nwrote %d unique urls to %s in %.1fs (%d requests)"
          % (len(rows), OUT, time.time() - t0, requests_made))
    d = START
    while d <= END:
        k = d.isoformat()
        print("%s\t%d" % (k, counts.get(k, 0)))
        d += timedelta(days=1)
    for must in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("check %s: %d (need 15)" % (must, counts.get(must, 0)))


if __name__ == "__main__":
    main()
