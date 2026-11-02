#!/usr/bin/env python3
"""Wiener Zeitung (wienerzeitung.at) article URLs for 2026-09-25..2026-10-25.

Route (all through polite_fetch, robots.txt of the outlet allows everything for
User-agent: *, it only blocks named AI crawlers):

1. https://www.wienerzeitung.at/robots.txt names sitemap-a-index.xml, sitemap-news.xml,
   sitemap-c.xml, sitemap-d.xml ...  sitemap-a-0.xml holds 1970 article <loc>s but NO
   <lastmod> and is not in publication order, so it cannot be dated.
2. sitemap-c.xml lists every section river page /c/<section>/<page> (8 sections:
   gesellschaft, politik, standort-oesterreich, wissenschaft, geschichte, kultur,
   europa, culpa).
3. Each section river page embeds its teasers as a Nuxt/Storyblok props blob, twice, in
   the HTML-escaped form
       full_slug&quot;:[0,&quot;a/<slug>&quot;],&quot;first_published_at&quot;:[0,&quot;2026-10-27T04:00:00.483Z&quot;]
   first_published_at is the publication timestamp: on 4 re-fetched articles it equals
   the page's JSON-LD "datePublished" (to the second). So listing pages alone give
   URL + date, with no per-article fetch.
   The rivers are strictly newest-first (gesellschaft p1: 10-27..10-10, p2: 10-09..09-17,
   p3: 09-11..08-23), so we walk each section until the NEWEST item on a page is older
   than the window start.
4. sitemap-news.xml (Google News sitemap, last 100 articles with <news:publication_date>)
   is unioned in as a cross-check / safety net.

Volume: the outlet published only 65 articles in the 31-day window (~2/day); the exactly
same 65 URLs come out of both routes (0 missing, 0 extra), so the per-day counts
(2026-09-30: 4, 2026-10-10: 2, 2026-10-20: 3) are the real publication volume, not a
coverage failure.  No date is invented: every date is the site's own first_published_at
or <news:publication_date>.
"""
import datetime as dt
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = Path("data/urls_custom/wienerzeitung-at.tsv")
BASE = "https://www.wienerzeitung.at"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
DEFAULT_SECTIONS = ["gesellschaft", "politik", "standort-oesterreich", "wissenschaft",
                    "geschichte", "kultur", "europa", "culpa"]
MAX_PAGES = 12

PAIR = re.compile(r'full_slug&quot;:\[0,&quot;([^&"]+?)&quot;\],&quot;first_published_at&quot;:\[0,&quot;([^&"]+?)&quot;\]')
PAIR_PLAIN = re.compile(r'"full_slug":\[0,"([^"]+?)"\],"first_published_at":\[0,"([^"]+?)"\]')


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception:
            status, text = None, None
        if status == 200 and text:
            return text
        if status in (403, 429, 500, 502, 503, 504, None):
            continue
        return None
    return None


def pairs_from(text):
    if not text:
        return []
    found = PAIR.findall(text)
    if not found:
        found = PAIR_PLAIN.findall(text)
        if not found:
            found = PAIR.findall(html.unescape(text))
    out = []
    for slug, iso in found:
        slug = html.unescape(slug)
        if not slug.startswith("a/"):
            continue
        try:
            d = dt.date.fromisoformat(iso[:10])
        except ValueError:
            continue
        out.append((slug, d))
    return out


def sections():
    text = get(f"{BASE}/sitemap-c.xml")
    if not text:
        return DEFAULT_SECTIONS
    names = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", text):
        m = re.match(r".*/c/([^/]+)/\d+", loc)
        if m and m.group(1) not in names:
            names.append(m.group(1))
    return names or DEFAULT_SECTIONS


def from_news_sitemap(found):
    text = get(f"{BASE}/sitemap-news.xml")
    if not text:
        return 0
    added = 0
    for loc, iso in re.findall(
            r"<loc>([^<]+)</loc>\s*<news:news>.*?<news:publication_date>([^<]+)</news:publication_date>",
            text, re.S):
        try:
            d = dt.date.fromisoformat(iso.strip()[:10])
        except ValueError:
            continue
        if START <= d <= END and loc not in found:
            found[loc] = d
            added += 1
    return added


def main():
    found = {}          # url -> date
    stats = []
    for sec in sections():
        pages = 0
        for p in range(1, MAX_PAGES + 1):
            text = get(f"{BASE}/c/{sec}/{p}")
            pages += 1
            items = pairs_from(text)
            if not items:
                break
            for slug, d in items:
                found.setdefault(f"{BASE}/{slug}", d)
            if max(d for _, d in items) < START:   # river is newest-first
                break
        stats.append(f"{sec}:{pages}")
    added = from_news_sitemap(found)

    rows, per_day = [], {}
    for url, d in found.items():
        if START <= d <= END:
            rows.append((url, d))
            per_day[d] = per_day.get(d, 0) + 1
    rows.sort(key=lambda r: (r[1], r[0]))
    seen, lines = set(), []
    for url, d in rows:
        if url in seen:
            continue
        seen.add(url)
        lines.append(f"{url}\t{d.isoformat()}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print("pages per section:", " ".join(stats))
    print("news sitemap added:", added)
    print("total URLs written:", len(lines))
    for day in sorted(per_day):
        print(day.isoformat(), per_day[day])


if __name__ == "__main__":
    main()
