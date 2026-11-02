#!/usr/bin/env python3
"""Radio Antsiva (antsiva.mg) — article URLs for 2026-09-25..2026-10-25.

All HTTP goes through scrapers/polite_fetch.py (robots.txt first, per-host rate
limit, every request logged).

Routes tried, in order (each one is a real attempt, results logged to stdout):
  1. robots.txt Sitemap: lines -> sitemap index / urlset, <lastmod> as date
  2. WordPress REST /wp-json/wp/v2/posts with after/before (site-local dates)
  3. feeds: /feed/, /rss, /rss.xml, /atom.xml, /sitemap-news.xml,
     /news-sitemap.xml, /wp-sitemap.xml
  4. home page + section pages: follow same-host links, accept an article only
     when the page itself states a date (JSON-LD datePublished, meta
     article:published_time, <time datetime>) inside the window
  5. Wayback CDX for the window (documented fallback; date = capture timestamp)

Output: data/urls_custom/antsiva-mg.tsv, "URL<TAB>YYYY-MM-DD", no header,
unique URLs, then a per-day count printout.

Finding on 2026-10-27: antsiva.mg is a single-page placeholder ("Eo
am-panamboarana ny tranonkala. Ho avy tsy ho ela." = the website is under
construction). Its own /sitemap.xml lists exactly one URL (the home page), its
JS bundle registers only the routes "/" and "/sitemap.xml", every other path
answers 404, and Wayback has 7 captures in total for the host (all the home
page and its assets, 2026-10-06). So this script currently writes 0 rows; the
routes above are kept so it works the day the outlet starts publishing.
"""

import json
import re
import sys
import html
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://antsiva.mg"
WINDOW_START = date(2026, 9, 25)
WINDOW_END = date(2026, 10, 25)
OUT = "data/urls_custom/antsiva-mg.tsv"

MAX_REQUESTS = 60
REQUEST_COUNT = 0
LOG = []


def log(msg):
    LOG.append(msg)
    print(msg, flush=True)


def get(url, timeout=25):
    """polite_fetch wrapper with a hard request budget."""
    global REQUEST_COUNT
    if REQUEST_COUNT >= MAX_REQUESTS:
        log(f"  budget exhausted, skipping {url}")
        return None, None
    REQUEST_COUNT += 1
    try:
        status, text, robots = fetch(url, timeout=timeout) if _accepts_timeout() else fetch(url)
    except Exception as exc:  # network, robots, parse
        log(f"  ERR  {url} -> {type(exc).__name__}: {str(exc)[:80]}")
        return None, None
    log(f"  {status:<4} {url} ({len(text) if text else 0} bytes, robots={robots})")
    return status, text


def _accepts_timeout():
    import inspect

    try:
        return "timeout" in inspect.signature(fetch).parameters
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- date helpers

ISO = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def date_in_window(d):
    return d is not None and WINDOW_START <= d <= WINDOW_END


def parse_iso_date(value):
    """Take the date part of an ISO timestamp (site-local date as stated)."""
    if not value:
        return None
    m = ISO.search(value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def page_date(text):
    """The date a page states about itself."""
    if not text:
        return None
    # JSON-LD datePublished (the site's own statement, most reliable)
    for block in re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S | re.I
    ):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            m = re.search(r'"%s"\s*:\s*"([^"]+)"' % key, block)
            d = parse_iso_date(m.group(1)) if m else None
            if d:
                return d
    # OpenGraph / article meta
    for pat in (
        r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',
        r'content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time',
        r'name=["\']pubdate["\'][^>]*content=["\']([^"\']+)',
        r'itemprop=["\']datePublished["\'][^>]*content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)',
    ):
        m = re.search(pat, text, re.I)
        d = parse_iso_date(m.group(1)) if m else None
        if d:
            return d
    # <time datetime="...">
    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)', text, re.I)
    d = parse_iso_date(m.group(1)) if m else None
    if d:
        return d
    return None


def page_text_len(text):
    if not text:
        return 0
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return len(re.sub(r"\s+", " ", html.unescape(body)).strip())


def is_article_url(url):
    """Reject the home page, assets, feeds, pagination, taxonomy pages."""
    p = urlparse(url)
    if p.netloc and p.netloc not in ("antsiva.mg", "www.antsiva.mg"):
        return False
    path = p.path.rstrip("/")
    if path == "":
        return False
    if re.search(r"\.(css|js|png|jpe?g|gif|svg|avif|webp|ico|woff2?|xml|json|txt|mp3|mp4|pdf)$", path, re.I):
        return False
    if re.search(r"/(feed|rss|atom|wp-json|wp-admin|wp-content|assets|__l5e|category|tag|author|page)(/|$)", path, re.I):
        return False
    if re.search(r"/(sitemap|robots)", path, re.I):
        return False
    return True


# ------------------------------------------------------------------- sitemaps

LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
LASTMOD = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)
NEWSPUB = re.compile(r"<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>", re.I)


def parse_sitemap(text, found):
    """Collect (url, date) from a urlset; return child sitemap URLs."""
    if not text:
        return []
    if "<sitemapindex" in text:
        return LOC.findall(text)
    children = []
    for chunk in re.findall(r"(?is)<url>(.*?)</url>", text):
        m = LOC.search(chunk)
        if not m:
            continue
        loc = html.unescape(m.group(1))
        raw = NEWSPUB.search(chunk) or LASTMOD.search(chunk)
        d = parse_iso_date(raw.group(1)) if raw else None
        if d and date_in_window(d) and is_article_url(loc):
            found[loc] = d
    if not children and "<urlset" not in text:
        # some servers hand out a bare list of <loc> without the wrapper
        locs = [html.unescape(x) for x in LOC.findall(text)]
        for loc in locs:
            if is_article_url(loc):
                found.setdefault(loc, None)
    return children


def route_sitemaps(found):
    log("[1] robots.txt Sitemap lines -> sitemaps")
    status, robots = get(BASE + "/robots.txt")
    seeds = []
    if robots:
        seeds = re.findall(r"(?im)^\s*sitemap:\s*(\S+)\s*$", robots)
        log(f"  robots sitemap lines: {seeds}")
        if re.search(r"(?im)^\s*user-agent:\s*\*\s*$[\s\S]{0,80}?^\s*disallow:\s*/\s*$", robots):
            log("  robots disallows everything for * -> sitemap route closed")
            return
    for default in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
                    "/wp-sitemap.xml", "/sitemap-news.xml", "/news-sitemap.xml"):
        if BASE + default not in seeds:
            seeds.append(BASE + default)
    queue = list(dict.fromkeys(seeds))
    seen = set()
    while queue and len(seen) < 12:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        status, text = get(sm)
        if status != 200 or not text:
            continue
        children = parse_sitemap(text, found)
        for child in children:
            if child not in seen:
                queue.append(html.unescape(child))
    log(f"  sitemap route collected {len(found)} in-window candidates")


# ------------------------------------------------------------------ REST/feeds

def route_rest(found):
    log("[2] WordPress REST")
    after = (WINDOW_START - timedelta(days=1)).isoformat() + "T00:00:00"
    before = (WINDOW_END + timedelta(days=1)).isoformat() + "T00:00:00"
    for page in range(1, 6):
        url = (f"{BASE}/wp-json/wp/v2/posts?per_page=100&_fields=link,date"
               f"&after={after}&before={before}&orderby=date&order=desc&page={page}")
        status, text = get(url)
        if status != 200 or not text:
            return
        try:
            rows = json.loads(text)
        except ValueError:
            return
        if not isinstance(rows, list) or not rows:
            return
        for row in rows:
            link = row.get("link")
            d = parse_iso_date(row.get("date"))
            if link and d and date_in_window(d) and is_article_url(link):
                found.setdefault(link, d)


def route_feeds(found):
    log("[3] RSS / Atom feeds")
    for path in ("/feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml", "/feed.xml"):
        status, text = get(BASE + path)
        if status != 200 or not text or "<rss" not in text and "<feed" not in text:
            continue
        for item in re.findall(r"(?is)<(?:item|entry)\b.*?</(?:item|entry)>", text):
            m = re.search(r"<link>\s*([^<\s]+)\s*</link>", item)
            if not m:
                m = re.search(r'<link[^>]+href=["\']([^"\']+)', item)
            if not m:
                continue
            link = html.unescape(m.group(1))
            raw = re.search(r"<(?:pubDate|published|updated|dc:date)>\s*([^<]+)<", item)
            d = None
            if raw:
                d = parse_iso_date(raw.group(1))
                if d is None:
                    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                                "%Y-%m-%dT%H:%M:%S%z", "%d %b %Y %H:%M:%S %z"):
                        try:
                            d = datetime.strptime(raw.group(1).strip(), fmt).date()
                            break
                        except ValueError:
                            continue
            if is_article_url(link) and d and date_in_window(d):
                found.setdefault(link, d)


# -------------------------------------------------------------- link crawling

def extract_links(text, page_url):
    links = []
    for m in re.finditer(r'href=["\']([^"\'#]+)', text or ""):
        link = urljoin(page_url, html.unescape(m.group(1)))
        link = link.split("?")[0]
        if link.startswith(("http://", "https://")) and is_article_url(link):
            links.append(link)
    return list(dict.fromkeys(links))


def route_crawl(found):
    log("[4] home page + section links, date read from each page")
    status, home = get(BASE + "/")
    if status != 200 or not home:
        return
    seeds = [BASE + p for p in ("/", "/vaovao", "/vaovao/", "/actualites", "/news",
                                "/lahatsoratra", "/archives")]
    candidates = extract_links(home, BASE + "/")
    for seed in seeds[1:]:
        st, text = get(seed)
        if st == 200 and text:
            candidates.extend(extract_links(text, seed))
    candidates = list(dict.fromkeys(candidates))
    log(f"  {len(candidates)} same-host article-shaped links to inspect")
    for link in candidates[:24]:
        st, text = get(link)
        if st != 200 or not text or page_text_len(text) < 200:
            continue
        d = page_date(text)
        if d and date_in_window(d):
            found.setdefault(link, d)


# --------------------------------------------------------------------- Wayback

def route_cdx(found):
    log("[5] Wayback CDX for the window")
    url = (f"http://web.archive.org/cdx/search/cdx?url=antsiva.mg/*"
           f"&from={WINDOW_START.strftime('%Y%m%d')}&to={WINDOW_END.strftime('%Y%m%d')}"
           f"&output=json&collapse=urlkey&fl=timestamp,original,statuscode&limit=500")
    for attempt in range(2):
        status, text = get(url, timeout=60)
        if status == 200 and text:
            try:
                rows = json.loads(text)
            except ValueError:
                return
            for row in rows[1:]:
                if len(row) < 3 or row[2] != "200":
                    continue
                original = row[1]
                if not is_article_url(original):
                    continue
                try:
                    d = datetime.strptime(row[0][:8], "%Y%m%d").date()
                except ValueError:
                    continue
                if date_in_window(d):
                    found.setdefault(original, d)
            log(f"  cdx rows={len(rows) - 1}")
            return
        log("  cdx unavailable, retrying once")


# ----------------------------------------------------------------------- main

def main():
    found = {}
    for route in (route_sitemaps, route_rest, route_feeds, route_crawl, route_cdx):
        try:
            route(found)
        except Exception as exc:
            log(f"  route {route.__name__} failed: {type(exc).__name__}: {str(exc)[:120]}")

    # keep only rows with a site-stated date inside the window, one per URL
    rows = sorted(
        ((u, d) for u, d in found.items() if d and date_in_window(d)),
        key=lambda r: (r[1], r[0]),
    )
    seen = set()
    unique = []
    for url, d in rows:
        if url in seen:
            continue
        seen.add(url)
        unique.append((url, d))

    with open(OUT, "w", encoding="utf-8") as fh:
        for url, d in unique:
            fh.write(f"{url}\t{d.isoformat()}\n")

    counts = {}
    for _, d in unique:
        counts[d.isoformat()] = counts.get(d.isoformat(), 0) + 1
    print(f"\nwrote {len(unique)} URLs to {OUT}")
    print(f"requests used: {REQUEST_COUNT}")
    print("per-day counts:")
    day = WINDOW_START
    while day <= WINDOW_END:
        key = day.isoformat()
        print(f"  {key}  {counts.get(key, 0)}")
        day += timedelta(days=1)
    if not unique:
        print("\nnothing in the window: antsiva.mg serves a single page "
              "(\"Eo am-panamboarana ny tranonkala\" — under construction) and its "
              "own /sitemap.xml lists only the home page; /vaovao and every other "
              "path answer 404.")


if __name__ == "__main__":
    main()
