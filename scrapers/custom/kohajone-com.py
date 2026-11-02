#!/usr/bin/env python3
"""kohajone.com (Koha Jone, Albania) -- article URLs published 2026-09-25..2026-10-25.

Route: the site is WordPress, its REST API is open and robots.txt only disallows
/wp-admin/ (robots.txt also advertises /sitemap.xml, used as a fallback).

  GET https://kohajone.com/wp-json/wp/v2/posts
      ?after=2026-09-25T00:00:00&before=2026-10-26T00:00:00
      &per_page=100&page=N&orderby=date&order=desc
      &_fields=date,link,content,title

'date' is the site's own publication date (site-local time), and 'content.rendered'
is the article body, which lets us keep the articles that carry real text.

Why the length filter: a large share of this outlet's output are 2-4 sentence
briefs (300-900 characters of body text); those are also the pages that fail the
downstream "1500+ characters of article text" requirement. We keep every item with
at least MIN_TEXT characters of body text (1700 keeps a
comfortable margin over the downstream 1500-character article-text floor) and top a short day back up to
MIN_PER_DAY with the longest of the rest, so no day is starved.

Output: data/urls_custom/kohajone-com.tsv, "URL<TAB>YYYY-MM-DD", no header, unique.
"""
import html
import json
import os
import re
import sys
import time

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, os.path.join(REPO, "scrapers"))

from polite_fetch import fetch  # noqa: E402

API = "https://kohajone.com/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
AFTER = START + "T00:00:00"
BEFORE = "2026-10-26T00:00:00"
MIN_TEXT = 1700      # characters of article body text
MIN_PER_DAY = 15     # never leave a day with fewer than this
SITEMAP_INDEX = "https://kohajone.com/sitemap.xml"
OUT = os.path.join(REPO, "data", "urls_custom", "kohajone-com.tsv")


def strip_html(h):
    h = re.sub(r"<script.*?</script>", " ", h or "", flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def get(url, tries=4):
    """polite_fetch with a few retries; returns (status, text)."""
    status, text = 0, None
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as exc:  # network hiccup
            status, text = 0, None
            sys.stderr.write("fetch error %s: %s\n" % (url, exc))
        if status == 200 and text:
            return status, text
        if status in (400, 404):  # invalid page: no point retrying
            return status, text
        time.sleep(3 + 5 * i)
    return status, text


def fetch_rest():
    """All posts in the window from the WP REST API, as (link, date, textlen)."""
    rows = []
    page = 1
    while page <= 200:
        url = (
            API + "?after=" + AFTER + "&before=" + BEFORE
            + "&per_page=100&page=%d&orderby=date&order=desc"
            "&_fields=date,link,content,title" % page
        )
        status, text = get(url)
        if status != 200 or not text:
            sys.stderr.write("REST stop at page %d (status %s)\n" % (page, status))
            break
        try:
            data = json.loads(text)
        except ValueError:
            sys.stderr.write("REST bad JSON at page %d\n" % page)
            break
        if not isinstance(data, list) or not data:
            break
        for p in data:
            link = (p.get("link") or "").strip()
            d = (p.get("date") or "")[:10]
            body = (p.get("content") or {}).get("rendered") or ""
            if not link or not d:
                continue
            rows.append((link, d, len(strip_html(body))))
        page += 1
    return rows


def fetch_sitemaps():
    """Fallback: walk the post sitemaps advertised in robots.txt, use <lastmod>."""
    rows = []
    status, text = get(SITEMAP_INDEX)
    if status != 200 or not text:
        return rows
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
    subs = [u for u in locs if u.endswith(".xml") or "sitemap" in u]
    if not subs:
        subs = [SITEMAP_INDEX]
    for sub in subs[:60]:
        s2, t2 = get(sub)
        if s2 != 200 or not t2:
            continue
        for m in re.finditer(r"<url>(.*?)</url>", t2, flags=re.S):
            block = m.group(1)
            loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
            mod = re.search(r"<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", block)
            if not loc or not mod:
                continue
            rows.append((loc.group(1).strip(), mod.group(1), MIN_TEXT))
    return rows


def main():
    rows = fetch_rest()
    route = "wp-json REST"
    if not rows:
        rows = fetch_sitemaps()
        route = "sitemap lastmod fallback"

    # dedupe by URL, keep the longest body seen for a URL
    best = {}
    for link, d, tlen in rows:
        if not (START <= d <= END):
            continue
        if not link.startswith("http"):
            continue
        prev = best.get(link)
        if prev is None or tlen > prev[1]:
            best[link] = (d, tlen)

    # per-day: keep the substantial articles, top a thin day up to MIN_PER_DAY
    by_day = {}
    for link, (d, tlen) in best.items():
        by_day.setdefault(d, []).append((link, tlen))

    kept = []
    for d in sorted(by_day):
        items = sorted(by_day[d], key=lambda x: -x[1])
        long_ones = [x for x in items if x[1] >= MIN_TEXT]
        if len(long_ones) < MIN_PER_DAY:
            long_ones += [x for x in items if x[1] < MIN_TEXT][: MIN_PER_DAY - len(long_ones)]
        kept.extend((link, d) for link, _ in long_ones)

    # unique URLs, sorted, no header
    final = sorted(set(kept))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for link, d in final:
            f.write("%s\t%s\n" % (link, d))
    os.replace(tmp, OUT)

    counts = {}
    for _, d in final:
        counts[d] = counts.get(d, 0) + 1
    print("route: %s | posts seen: %d | urls kept: %d | days: %d"
          % (route, len(best), len(final), len(counts)))
    for d in sorted(counts):
        print("%s  %d" % (d, counts[d]))

    missing = [d for d in (START, END) if d not in counts]
    thin = [d for d in ("2026-09-30", "2026-10-10", "2026-10-20") if counts.get(d, 0) < MIN_PER_DAY]
    if thin:
        print("WARNING thin days: %s" % ", ".join("%s=%d" % (d, counts.get(d, 0)) for d in thin))
    if missing:
        print("WARNING no urls for %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
