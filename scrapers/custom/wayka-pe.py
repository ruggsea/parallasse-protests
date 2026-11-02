#!/usr/bin/env python3
"""wayka.pe (Peru) — article URLs published 2026-09-25 .. 2026-10-25.

Route (probed 2026-10-27):
  robots.txt -> User-agent: Scrapy/1.6.0 / Disallow: /  — a rule for the *Scrapy* UA only.
      Our UA (ParallasseResearchBot) matches no group, so the site is open to us
      (checked with urllib.robotparser: can_fetch == True on /, /wp-json/..., /feed/).
      polite_fetch confirms path='fetched'.
  sitemaps   -> /wp-sitemap.xml is an EMPTY <urlset> (google-sitemap-generator 4.1.25
      emits nothing); /sitemap_index.xml 404. Sitemap route is closed.
  WP REST    -> /wp-json/wp/v2/posts?after=&before=&per_page=100 works: 200, JSON.
      'date' is site-local (America/Lima, UTC-5, no DST) and equals the page's
      JSON-LD datePublished converted to -05:00 (verified on
      /cusco-exigen-celeridad-y-justicia-por-presunta-violencia-sexual/ :
      REST 2026-10-15T12:07:19 == JSON-LD 2026-10-15T17:07:19+00:00).
  RSS        -> /feed/?paged=N, 5 items/page, <pubDate> in +0000; used as a
      cross-check / fallback with the same dates.

The outlet publishes only ~18 posts in the whole window (about one every two
days: 2026-09-30=1, 2026-10-10=0, 2026-10-20=0), so the 15-per-day bar cannot be
met by the site itself — the grid records low_volume instead.

Writes data/urls_custom/wayka-pe.tsv  (URL<TAB>YYYY-MM-DD, no header, unique).
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
from polite_fetch import fetch  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "data", "urls_custom", "wayka-pe.tsv")

BASE = "https://wayka.pe"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
LIMA = timezone(timedelta(hours=-5))  # Peru: fixed UTC-5, no DST
ARTICLE_RE = re.compile(r"^https://wayka\.pe/[a-z0-9][a-z0-9-]{3,}/$")
SKIP = {
    "actualidad", "audiovisual", "investigaciones", "opinion", "especiales",
    "quienes-somos", "contacto", "feed", "author", "category", "tag",
}


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def from_rest():
    """IDs/link+local date from the site's own WP REST API, paginated."""
    rows = []
    for page in range(1, 8):
        url = (
            f"{BASE}/wp-json/wp/v2/posts?per_page=100&page={page}"
            f"&after={START.isoformat()}T00:00:00&before={(END + timedelta(days=1)).isoformat()}T00:00:00"
            "&_fields=link,date&orderby=date&order=desc"
        )
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"  rest page {page}: HTTP {status}", file=sys.stderr)
            break
        try:
            data = json.loads(text)
        except ValueError:
            print(f"  rest page {page}: unparseable JSON", file=sys.stderr)
            break
        if not isinstance(data, list) or not data:
            break
        for it in data:
            link, dt = it.get("link"), it.get("date")
            if not link or not dt:
                continue
            rows.append((link.strip(), dt[:10]))
        if len(data) < 100:
            break
    print(f"  rest: {len(rows)} posts", file=sys.stderr)
    return rows


def from_feed():
    """Fallback / cross-check: RSS pages of 5 items, pubDate in +0000 -> Lima day."""
    rows = []
    for page in range(1, 13):
        url = f"{BASE}/feed/" if page == 1 else f"{BASE}/feed/?paged={page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            break
        items = re.findall(r"<item>(.*?)</item>", text, re.S)
        if not items:
            break
        stop = False
        for it in items:
            m_link = re.search(r"<link>\s*(https?://[^<\s]+?)\s*</link>", it)
            m_date = re.search(r"<pubDate>\s*([^<]+?)\s*</pubDate>", it)
            if not (m_link and m_date):
                continue
            try:
                dt = datetime.strptime(m_date.group(1), "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                continue
            local = dt.astimezone(LIMA)
            rows.append((m_link.group(1).strip(), local.date().isoformat()))
            if local.date() < START:
                stop = True
        if stop:
            break
    print(f"  feed: {len(rows)} items", file=sys.stderr)
    return rows


def keep(url, day):
    if not url.startswith(BASE + "/"):
        return False
    slug = url[len(BASE) + 1:].strip("/")
    if not slug or slug in SKIP or "/" in slug:
        return False
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    return START <= d <= END


def main():
    rows = from_rest()
    if len(rows) < 5:
        print("  rest thin/failed, falling back to RSS", file=sys.stderr)
        rows += from_feed()
    else:
        # cheap cross-check that costs 1 request; adds nothing unless REST missed it
        rows += from_feed()

    best = {}
    for url, day in rows:
        if not keep(url, day):
            continue
        url = url if url.endswith("/") else url + "/"
        if url not in best or day > best[url]:
            best[url] = day

    ordered = sorted(best.items(), key=lambda kv: (kv[1], kv[0]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, day in ordered:
            f.write(f"{url}\t{day}\n")
    os.replace(tmp, OUT)

    counts = {}
    for _, day in ordered:
        counts[day] = counts.get(day, 0) + 1
    print(f"wrote {len(ordered)} unique URLs to {OUT}")
    for d in daterange(START, END):
        k = d.isoformat()
        print(f"{k}\t{counts.get(k, 0)}")
    for k in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"target {k}: {counts.get(k, 0)} URLs")


if __name__ == "__main__":
    main()
