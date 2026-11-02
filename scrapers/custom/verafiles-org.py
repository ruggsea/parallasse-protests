#!/usr/bin/env python3
"""VERA Files (verafiles.org) - article URLs published 2026-09-25 .. 2026-10-25.

Route: the site's own WordPress REST API
    /wp-json/wp/v2/posts?_fields=link,date&per_page=100&after=&before=
robots.txt is a 404 (assumed open), the REST endpoint answers 200 and its
local 'date' field is the publication time in Asia/Manila (+08:00) - it equals
the page's JSON-LD datePublished converted to +08:00.

Fallback (only if REST yields nothing): the newest post-sitemapN.xml files give
candidate URLs; each page is then fetched and dated from its JSON-LD
datePublished / article:published_time, converted to +08:00.

Writes data/urls_custom/verafiles-org.tsv : URL<TAB>YYYY-MM-DD, one per line.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/verafiles-org.tsv"

START = "2026-09-25"
END = "2026-10-25"
PHT = timezone(timedelta(hours=8))

API = ("https://verafiles.org/wp-json/wp/v2/posts"
       "?per_page=100&_fields=link,date"
       "&after=" + START + "T00:00:00&before=" + END + "T23:59:59&page={}")


def in_window(day):
    return START <= day <= END


def rest_posts(rows):
    """Collect (url, day) from the WP REST API. Returns number of requests made."""
    reqs = 0
    for page in range(1, 8):
        url = API.format(page)
        status, text, _ = fetch(url)
        reqs += 1
        if status in (429, 503):
            time.sleep(60)          # the site rate-limits bursts; one slow retry
            status, text, _ = fetch(url)
            reqs += 1
        if status != 200 or not text:
            break
        try:
            data = json.loads(text)
        except ValueError:
            break
        if not isinstance(data, list) or not data:
            break
        for item in data:
            link = (item.get("link") or "").strip()
            date = (item.get("date") or "").strip()
            if not link or len(date) < 10:
                continue
            day = date[:10]
            if in_window(day):
                rows.setdefault(link, day)
        if len(data) < 100:
            break
    return reqs


def page_date(html):
    """Publication date of an article page, as a PHT calendar day."""
    stamps = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if not stamps:
        stamps = re.findall(
            r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
            html)
    if not stamps:
        stamps = re.findall(r'<time[^>]+datetime=["\']([^"\']+)["\']', html)
    for s in stamps:
        s = s.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(PHT).strftime("%Y-%m-%d")
    return None


def rss_fallback(rows):
    """Date articles from the site feed (10 items/page, pubDate in GMT)."""
    reqs = 0
    for page in range(1, 15):
        url = ("https://verafiles.org/feed/" if page == 1
               else f"https://verafiles.org/feed/?paged={page}")
        status, text, _ = fetch(url)
        reqs += 1
        if status != 200 or not text:
            break
        items = re.findall(r"<item>(.*?)</item>", text, re.S)
        if not items:
            break
        oldest = None
        for item in items:
            link = re.search(r"<link>\s*([^<\s]+)\s*</link>", item)
            pub = (re.search(r"<pubDate>([^<]+)</pubDate>", item)
                   or re.search(r"<dc:date>([^<]+)</dc:date>", item))
            if not link or not pub:
                continue
            try:
                dt = datetime.strptime(pub.group(1).strip(),
                                       "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                continue
            day = dt.astimezone(PHT).strftime("%Y-%m-%d")
            oldest = day if oldest is None or day < oldest else oldest
            if in_window(day):
                rows.setdefault(link.group(1).strip(), day)
        if oldest is not None and oldest < START:
            break
    return reqs


def sitemap_fallback(rows):
    """Date article pages found in the newest post sitemaps (only used if REST failed)."""
    reqs = 0
    status, text, _ = fetch("https://verafiles.org/sitemap.xml")
    reqs += 1
    if status != 200 or not text:
        return reqs
    subs = re.findall(r"<loc>([^<]*post-sitemap(\d*)\.xml)</loc>", text)
    subs = sorted(subs, key=lambda m: int(m[1] or 1), reverse=True)[:2]
    candidates = []
    for url, _n in subs:
        st, body, _ = fetch(url)
        reqs += 1
        if st != 200 or not body:
            continue
        for loc, lastmod in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", body):
            # lastmod on this site is last-edit time, so only use it to skip
            # definitively old entries (older than a month before the window).
            if lastmod[:10] >= "2026-08-25":
                candidates.append(loc)
    fails = 0
    for loc in candidates[:80]:
        if loc in rows:
            continue
        st, body, _ = fetch(loc)
        reqs += 1
        if st != 200 or not body:
            fails += 1
            if fails >= 3:          # page views are rate-limited hard; stop early
                break
            continue
        fails = 0
        day = page_date(body)
        if day and in_window(day):
            rows[loc] = day
    return reqs


def main():
    rows = {}
    reqs = rest_posts(rows)
    if len(rows) < 10:
        reqs += sitemap_fallback(rows)
    if len(rows) < 10:
        reqs += rss_fallback(rows)

    per_day = {}
    for url, day in rows.items():
        per_day.setdefault(day, []).append(url)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for day in sorted(per_day):
        for url in sorted(per_day[day]):
            lines.append(f"{url}\t{day}\n")
    OUT.write_text("".join(lines))

    print(f"verafiles.org: {len(rows)} unique URLs, {len(per_day)} days, {reqs} requests")
    for day in sorted(per_day):
        print(f"  {day}\t{len(per_day[day])}")


if __name__ == "__main__":
    main()
