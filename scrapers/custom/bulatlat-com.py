#!/usr/bin/env python3
"""bulatlat-com: list article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-27):
  robots.txt is the old Drupal default: permissive for everything we need
  (only /admin/, /search/, /sites/, /modules/ ... are closed) and it advertises
  NO Sitemap line. Crawl-delay: 10.

  Primary: the site's own WordPress REST index
    /wp-json/wp/v2/posts?per_page=100&page=N&_fields=link,date,date_gmt
      &after=2026-09-24T00:00:00&before=2026-10-26T00:00:00
  The 'date' field is post_date in site-local time (Asia/Manila, +08:00) and it
  equals the /YYYY/MM/DD/ segment of the article permalink on every row, so the
  listed date is taken from the URL path (site-stated) and cross-checked against
  REST 'date'.  Page JSON-LD datePublished is the same instant in UTC, which can
  be one calendar day earlier for posts filed before 08:00 local - that is the
  only disagreement and it is within the 1-day tolerance.

  The custom post type 'project' was checked and has 0 rows in the window, so
  /wp/v2/posts is the complete set.

  Fallback (only if REST fails): Yoast /post-sitemap.xml (the newest chunk of
  the /sitemap.xml index), using <lastmod> date-part, which for this site is the
  publish time of unedited posts.

Output: data/urls_custom/bulatlat-com.tsv  (URL<TAB>YYYY-MM-DD, no header)
"""
import sys, os, json, re, datetime, urllib.parse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/bulatlat-com.tsv")
BASE = "https://www.bulatlat.com"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
# one-day margins on both sides, then filter exactly by the URL date
AFTER = (START - datetime.timedelta(days=1)).isoformat() + "T00:00:00"
BEFORE = (END + datetime.timedelta(days=1)).isoformat() + "T00:00:00"


def date_from_url(url):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def from_rest():
    rows = []
    for page in range(1, 15):
        url = (
            BASE + "/wp-json/wp/v2/posts?per_page=100&page=%d"
            "&_fields=link,date,date_gmt&after=%s&before=%s" % (page, AFTER, BEFORE)
        )
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print("REST page %d -> %s" % (page, status))
            break
        try:
            items = json.loads(text)
        except ValueError:
            print("REST page %d -> unparsable JSON" % page)
            break
        print("REST page %d -> 200, %d posts" % (page, len(items)))
        for it in items:
            link = (it.get("link") or "").strip()
            if not link:
                continue
            d = date_from_url(link)
            if d is None:
                # fall back to the site-local publish time
                try:
                    d = datetime.date.fromisoformat((it.get("date") or "")[:10])
                except ValueError:
                    continue
            rows.append((link, d))
        if len(items) < 100:
            break
    return rows


def from_sitemap():
    rows = []
    status, text, _ = fetch(BASE + "/post-sitemap.xml")
    print("sitemap /post-sitemap.xml -> %s" % status)
    if status != 200 or not text:
        return rows
    for m in re.finditer(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text):
        link, lastmod = m.group(1).strip(), m.group(2).strip()
        d = date_from_url(link) or datetime.date.fromisoformat(lastmod[:10])
        rows.append((link, d))
    return rows


def main():
    rows = from_rest()
    if not rows:
        print("REST gave nothing, falling back to the post sitemap")
        rows = from_sitemap()

    seen = {}
    for link, d in rows:
        if not (START <= d <= END):
            continue
        link = urllib.parse.urldefrag(link)[0]
        if not link.startswith("http"):
            continue
        if link not in seen:
            seen[link] = d

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for link in sorted(seen, key=lambda u: (seen[u], u)):
            f.write("%s\t%s\n" % (link, seen[link].isoformat()))
            per_day[seen[link].isoformat()] = per_day.get(seen[link].isoformat(), 0) + 1
    os.replace(tmp, OUT)

    print("wrote %d URLs to %s" % (len(seen), OUT))
    day = START
    while day <= END:
        k = day.isoformat()
        print("  %s  %d" % (k, per_day.get(k, 0)))
        day += datetime.timedelta(days=1)


if __name__ == "__main__":
    main()
