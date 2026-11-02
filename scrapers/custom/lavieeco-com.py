#!/usr/bin/env python3
"""La Vie éco (lavieeco.com) — article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt (www.lavieeco.com) disallows /wp-json/, /feed/, /comments/ — so the
WordPress REST API and RSS are closed.  It advertises https://www.lavieeco.com/sitemap_index.xml
(Yoast SEO).  The index lists 427 post-sitemap files, post-sitemap427.xml being the newest
(200 URLs each, ordered ascending by <lastmod>).  Walking the newest file downwards until a
file's newest <lastmod> predates the window covers the window in 4-5 requests.

Date: <lastmod> is the publication time here — on the article checked it equals the page's
JSON-LD datePublished to the second (2026-10-13T20:34:01+00:00).  The script re-checks a few
sampled articles each run against their own JSON-LD datePublished and prints the result.

Volume: the outlet publishes ~20 articles on weekdays and very little at the weekend
(2026-10-03=3, 2026-10-11=5), so 2026-10-10 (a Saturday) holds 7 posts in the sitemap.

Writes data/urls_custom/lavieeco-com.tsv  (URL <TAB> YYYY-MM-DD, no header, unique URLs).
"""
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.lavieeco.com"
OUT = "data/urls_custom/lavieeco-com.tsv"
START, END = "2026-09-25", "2026-10-25"

URL_RE = re.compile(r"<url>(.*?)</url>", re.S)
LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
LM_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S)


def parse_urlset(xml):
    """[(loc, lastmod_date or '')] from a sitemap urlset."""
    out = []
    for block in URL_RE.findall(xml):
        loc = LOC_RE.search(block)
        if not loc:
            continue
        lm = LM_RE.search(block)
        out.append((loc.group(1).strip(), lm.group(1).strip()[:10] if lm else ""))
    return out


def newest_n():
    """Highest post-sitemapN.xml number the index names (0 = unsuffixed file only)."""
    status, xml, _ = fetch(BASE + "/sitemap_index.xml")
    if status != 200 or not xml:
        print("sitemap_index status=%s" % status, file=sys.stderr)
        return 1
    ns = [int(n) for n in re.findall(r"/post-sitemap(\d+)\.xml", xml)]
    return max(ns) if ns else 1


def main():
    top = newest_n()
    print("newest post-sitemap index:", top)

    rows = {}  # url -> lastmod date (earliest seen wins)
    files_read = 0
    # A stale index can lag a freshly created file; try the two above the advertised max.
    for n in (top + 2, top + 1, top) + tuple(range(top - 1, max(top - 12, 0), -1)):
        if files_read >= 12:
            break
        status, xml, _ = fetch("%s/post-sitemap%d.xml" % (BASE, n))
        if status == 404 or not xml:
            continue
        items = parse_urlset(xml)
        if not items:
            continue
        files_read += 1
        dated = [d for _, d in items if d]
        oldest = min(dated) if dated else ""
        newest = max(dated) if dated else ""
        print("  post-sitemap%d.xml: %d urls, %s .. %s" % (n, len(items), oldest, newest))
        for loc, d in items:
            if not d:
                continue
            if loc not in rows or d < rows[loc]:
                rows[loc] = d
        if oldest and oldest < START:
            break

    # News sitemap: only the last ~48h, but it carries news:publication_date and catches
    # posts the post-sitemap has not picked up yet.
    status, xml, _ = fetch(BASE + "/news-sitemap.xml")
    if status == 200 and xml:
        add = 0
        for loc, d in parse_urlset(xml):
            if d and START <= d <= END and loc not in rows:
                rows[loc] = d
                add += 1
        print("  news-sitemap.xml: %d urls, %d new in window" % (len(parse_urlset(xml)), add))
    else:
        print("  news-sitemap.xml status=%s (skipped)" % status)

    keep = {u: d for u, d in rows.items() if START <= d <= END}
    ordered = sorted(keep.items(), key=lambda kv: (kv[1], kv[0]))

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in ordered:
            f.write("%s\t%s\n" % (u, d))

    counts = Counter(d for _, d in ordered)
    print("wrote %d unique urls to %s" % (len(ordered), OUT))
    for day in sorted(counts):
        print("  %s\t%d" % (day, counts[day]))

    # Self-check: the listed date must be the date the article page states.
    bad = 0
    for u, d in ordered[:: max(1, len(ordered) // 5)][:5]:
        st, html, _ = fetch(u)
        if st != 200 or not html:
            print("  check %s -> HTTP %s" % (u, st))
            continue
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        pd = m.group(1)[:10] if m else "?"
        flag = "" if pd == d else "  <-- MISMATCH"
        if flag:
            bad += 1
        print("  check %s listed=%s page=%s%s" % (u.rsplit("/", 2)[-2][:40], d, pd, flag))
    print("self-check mismatches:", bad)


if __name__ == "__main__":
    main()
