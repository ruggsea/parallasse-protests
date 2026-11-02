#!/usr/bin/env python3
"""visao-pt (Visão, Portugal, https://visao.pt) -- article URLs published 2026-09-25..2026-10-25.

Route: robots.txt allows everything except /wp-admin/ and /*gen.pl (Crawl-delay 15, no Sitemap
line, but /sitemap_index.xml answers).  The site is WordPress + Yoast: /sitemap_index.xml lists
~6300 flat urlsets /post-sitemapN.xml, 100 URLs each, numbered in post-ID (= publication) order,
newest = highest N.  The window lives in the last handful of files, so we walk N downwards from
the highest N in the index (plus a couple of probes above it, in case the index lags) until a
file's newest post is older than the window start.

Listed date: the publication date the site itself writes into every article URL, i.e. the
/...YYYY-MM-DD-slug/ segment (== the page's JSON-LD datePublished, verified on samples).  For the
rare entry without a date in its path we fall back to the <lastmod> date (UTC), which Yoast sets
to the post's modified time and equals the publish date on unedited posts.

/w/was closed: /news-sitemap.xml 404, /sitemap.xml == the same index, WP REST /wp-json/ and
?rest_route= both 401, date archives /2026/09/30/ 404.
"""
import os
import re
import sys
import time
import collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/visao-pt.tsv")
INDEX = "https://visao.pt/sitemap_index.xml"
START, END = "2026-09-25", "2026-10-25"
MAX_FILES = 18

FN = re.compile(r"https://visao\.pt/post-sitemap(\d+)\.xml")
ENTRY = re.compile(r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", re.S)
PATHDATE = re.compile(r"/(20\d\d-\d\d-\d\d)-")


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception:
            status, text = 0, None
        if status == 200 and text:
            return text
        if status == 404:
            return None
        time.sleep(2 + 2 * i)
    return None


def entry_date(url, lastmod):
    m = PATHDATE.search(url)
    if m:
        return m.group(1)
    if lastmod and len(lastmod) >= 10:
        return lastmod[:10]
    return None


def fetch_file(n):
    """-> list of (url, date) or None if the file does not exist / is unreachable."""
    xml = get("https://visao.pt/post-sitemap%d.xml" % n)
    if not xml:
        return None
    out = []
    for url, lastmod in ENTRY.findall(xml):
        d = entry_date(url, lastmod)
        if d:
            out.append((url, d))
    return out


def main():
    rows = {}
    index = get(INDEX)
    if not index:
        sys.stderr.write("sitemap index unreachable\n")
    else:
        nums = sorted({int(m.group(1)) for m in FN.finditer(index)})
        top = nums[-1] if nums else 6280
        print("index: %d post-sitemaps, highest N=%d" % (len(nums), top))
        files = 0
        n = top + 2                       # index can lag behind the newest file
        oldest_seen = "9999-99-99"
        while n >= 1 and files < MAX_FILES:
            entries = fetch_file(n)
            if entries:
                files += 1
                newest = max(d for _, d in entries)
                oldest = min(d for _, d in entries)
                oldest_seen = min(oldest_seen, oldest)
                inwin = [(u, d) for u, d in entries if START <= d <= END]
                print("  post-sitemap%d.xml: %3d urls, dates %s..%s, in window %d"
                      % (n, len(entries), oldest, newest, len(inwin)))
                for u, d in inwin:
                    rows.setdefault(u, d)
                if newest < START and files >= 2:
                    break
                if oldest_seen < START and newest < START:
                    break
            n -= 1

    # Nothing collected (index/file route broken): try the site's own RSS feed as a thin fallback.
    if not rows:
        for page in range(1, 12):
            url = "https://visao.pt/feed/" if page == 1 else "https://visao.pt/feed/?paged=%d" % page
            xml = get(url)
            if not xml:
                break
            got = 0
            for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
                m = re.search(r"<link>(.*?)</link>", item)
                p = re.search(r"<pubDate>(.*?)</pubDate>", item)
                if not m or not p:
                    continue
                try:
                    d = time.strftime("%Y-%m-%d", time.strptime(p.group(1)[5:16].strip(), "%d %b %Y"))
                except Exception:
                    continue
                if START <= d <= END:
                    rows.setdefault(m.group(1).strip(), d)
                    got += 1
            if got == 0:
                break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lines = ["%s\t%s\n" % (u, d) for u, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))]
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(lines)
    os.replace(tmp, OUT)

    per_day = collections.Counter(d for _, d in rows.items())
    print("wrote %d unique urls to %s" % (len(rows), OUT))
    for d in sorted(per_day):
        print("  %s  %d" % (d, per_day[d]))
    for must in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("check day %s: %d" % (must, per_day.get(must, 0)))


if __name__ == "__main__":
    main()
