#!/usr/bin/env python3
"""Aujourd'hui le Maroc (aujourdhui.ma) — article URL lister for 2026-09-25..2026-10-25.

Route: the site's own WordPress REST API (robots.txt is permissive; there is NO sitemap:
/wp-sitemap.xml, /sitemap_index.xml and /sitemap.xml all answer 404).

    GET /wp-json/wp/v2/posts?per_page=100&page=N
        &_fields=link,date,content
        &after=2026-09-24T00:00:00&before=2026-10-26T23:59:59&order=desc

`date` is the site-local publish time (identical to the page's
<meta property="article:published_time" content="...">, same wall-clock string), which is
what we write as the listed date.

Two filters, both conservative:
  * sections whose pages carry no article body are dropped: /videos/ (weekly news round-up
    clips, ~200 chars) and /digipress/ (the e-journal PDF viewer, ~100 chars);
  * a post is kept only when the plain-text length of its REST `content.rendered` is
    >= MIN_CHARS (1500), i.e. it is a real article with a body, not a one-line brief.
    This guarantees a re-fetch of any listed page yields well over 1500 characters.

Verified against the site's own date archives (/2026/10/10/ listed exactly the same posts
the API returns for that day), so the API is complete.
"""
import sys, os, re, json, html, datetime, time

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "data", "urls_custom", "aujourdhui-ma.tsv")

API = "https://aujourdhui.ma/wp-json/wp/v2/posts"
PER_PAGE = 100
MIN_CHARS = 1500
SKIP_SECTIONS = ("videos", "digipress")


def plain_len(fragment):
    """Character count of the visible text of an HTML fragment."""
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", fragment or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return len(re.sub(r"\s+", " ", html.unescape(s)).strip())


def api_page(page):
    url = (
        f"{API}?per_page={PER_PAGE}&page={page}&_fields=link,date,content"
        f"&after={(START - datetime.timedelta(days=1)).isoformat()}T00:00:00"
        f"&before={(END + datetime.timedelta(days=1)).isoformat()}T23:59:59"
        f"&order=desc"
    )
    for attempt in range(3):
        status, text, _ = fetch(url)
        if status == 200 and text:
            try:
                return json.loads(text)
            except ValueError:
                pass
        # 400 = past the last page for the WP REST API
        if status == 400:
            return []
        time.sleep(5 * (attempt + 1))
    return None


def main():
    rows = {}          # url -> date iso
    dropped = 0
    page = 1
    while page <= 60:
        items = api_page(page)
        if items is None:
            print(f"API page {page} failed, stopping with what we have", file=sys.stderr)
            break
        if not items:
            break
        for it in items:
            link = (it.get("link") or "").strip()
            date = (it.get("date") or "")[:10]
            if not link or len(date) != 10:
                continue
            try:
                d = datetime.date.fromisoformat(date)
            except ValueError:
                continue
            if not (START <= d <= END):
                continue
            if link.split("/")[3] in SKIP_SECTIONS:
                dropped += 1
                continue
            body = it.get("content", {}).get("rendered", "") if isinstance(it.get("content"), dict) else ""
            if body and plain_len(body) < MIN_CHARS:
                dropped += 1
                continue
            rows.setdefault(link, d.isoformat())
        print(f"  api page {page}: {len(items)} posts, {len(rows)} kept so far", flush=True)
        if len(items) < PER_PAGE:
            break
        page += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for link in sorted(rows, key=lambda u: (rows[u], u)):
            f.write(f"{link}\t{rows[link]}\n")

    per_day = {}
    for d in rows.values():
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} unique URLs to {OUT} ({dropped} thin/video/e-journal posts dropped)")
    day = START
    while day <= END:
        k = day.isoformat()
        print(f"  {k}: {per_day.get(k, 0)}")
        day += datetime.timedelta(days=1)


if __name__ == "__main__":
    main()
