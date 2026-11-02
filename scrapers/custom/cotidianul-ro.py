#!/usr/bin/env python3
"""Cotidianul (cotidianul.ro) — article URLs published 2026-09-25 .. 2026-10-25.

Route (robots.txt of cotidianul.ro is permissive apart from /wp-admin/, /wp-json/,
/feed/, /trackback/, /xmlrpc.php; it advertises /sitemaps/*.xml):

  1. https://www.cotidianul.ro/sitemaps/sitemap-posts-index.xml  -> monthly flat
     urlsets sitemap-posts-YYYY-MM.xml.  <lastmod> is the publish instant in Romania
     local time (+03:00 / +02:00 after the 2026-10-25 DST flip) and equals the
     article's JSON-LD datePublished (verified).  Two files (2026-09, 2026-10) cover
     the whole window; no recursion.
  2. The September file is frozen at its build time 2026-09-30T04:32+03:00, so it
     holds only 1 post of 2026-09-30 (~35 missing) while the site really published
     31 that day.  Therefore any day whose sitemap count is below MIN_PER_DAY is
     topped up from the site's own WordPress date archive /YYYY/MM/DD/ (page title
     "Zi: 30 septembrie 2026", real publication-date archive, paginated): every
     post inside those <article> blocks is dated with the archive's own day.
     /wp-json/ is robots-disallowed and /?rest_route=/wp/v2/posts answers 403, so
     the archive is the only route for that day.

Writes data/urls_custom/cotidianul-ro.tsv (URL<TAB>YYYY-MM-DD, unique, no header).
"""
import re
import sys
import collections
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = ROOT + "/data/urls_custom/cotidianul-ro.tsv"

START = date(2026, 9, 25)
END = date(2026, 10, 25)
MIN_PER_DAY = 20          # below this, top up the day from the date archive
BASE = "https://www.cotidianul.ro"

MONTHS = []
d = date(START.year, START.month, 1)
while d <= END:
    MONTHS.append((d.year, d.month))
    d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def log(*a):
    print(*a, flush=True)


def parse_sitemap(xml):
    """(loc, lastmod-date) pairs from a flat urlset."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
        lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
        if not loc or not lm:
            continue
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lm.group(1))
        if not m:
            continue
        out.append((loc.group(1), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    return out


def archive_urls(day, max_pages=4):
    """Article URLs listed by the WordPress date archive /YYYY/MM/DD/ (+ /page/N/)."""
    got = []
    base = "%s/%04d/%02d/%02d/" % (BASE, day.year, day.month, day.day)
    seen_pages = set()
    page = 1
    while page <= max_pages:
        url = base if page == 1 else base + "page/%d/" % page
        if url in seen_pages:
            break
        seen_pages.add(url)
        status, html, _ = fetch(url)
        if status != 200 or not html:
            log("  archive %s -> %s" % (url, status))
            break
        # only the main listing: <article> ... </article> blocks
        blocks = re.findall(r"<article\b.*?</article>", html, re.S)
        found = []
        for b in blocks:
            # the post link is the anchor carrying class="entry-title"; category
            # links (/articole/actualitate/ ...) live in the same block, skip them
            m = re.search(r'<a\b[^>]*class="entry-title"[^>]*href="([^"]+)"', b) or \
                re.search(r'<a\b[^>]*href="([^"]+)"[^>]*class="entry-title"', b)
            if not m:
                continue
            u = m.group(1)
            if "/articole/" in u or "/category/" in u or "/autor/" in u or "/tag/" in u:
                continue
            if u.rstrip("/") == base.rstrip("/"):
                continue
            found.append(u)
        new = [u for u in dict.fromkeys(found) if u not in got]
        got.extend(new)
        log("  archive %s -> %s, %d article links" % (url, status, len(new)))
        if len(new) == 0:
            break
        page += 1
    return got


def main():
    rows = {}      # url -> date
    per_day = collections.Counter()

    # 1) monthly sitemaps
    for (y, m) in MONTHS:
        url = "%s/sitemaps/sitemap-posts-%04d-%02d.xml" % (BASE, y, m)
        status, xml, _ = fetch(url)
        if status != 200 or not xml:
            log("sitemap %s -> %s" % (url, status))
            continue
        pairs = parse_sitemap(xml)
        kept = 0
        for loc, day in pairs:
            if START <= day <= END:
                if loc not in rows:
                    rows[loc] = day
                    per_day[day] += 1
                    kept += 1
        log("sitemap %s -> 200, %d urls, %d in window" % (url, len(pairs), kept))

    # 2) top up thin days from the site's own date archive
    day = START
    while day <= END:
        if per_day[day] < MIN_PER_DAY:
            log("top-up %s (sitemap had %d)" % (day, per_day[day]))
            for u in archive_urls(day):
                if u not in rows and START <= day <= END:
                    rows[u] = day
                    per_day[day] += 1
        day += timedelta(days=1)

    # 3) write
    ordered = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as f:
        for u, day in ordered:
            f.write("%s\t%s\n" % (u, day.isoformat()))

    log("\nwrote %d urls to %s" % (len(ordered), OUT))
    for day in sorted(per_day):
        if per_day[day]:
            log("  %s  %d" % (day, per_day[day]))
    log("  total %d" % sum(per_day.values()))


if __name__ == "__main__":
    main()
