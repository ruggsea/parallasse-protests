#!/usr/bin/env python3
"""donya-e-eqtesad.com (Donya-e-Eqtesad, Iran) URL lister for 2026-09-25..2026-10-25.

Route: robots.txt is permissive and names https://donya-e-eqtesad.com/sitemap.xml.
That index is a <sitemapindex> whose <loc> paths are base64url (no padding) JSON
query descriptors, e.g. {"model":"newsstudioPage","page":975,"perPage":2000}.
Each of those entries is a flat <urlset> holding ~2000 article URLs with a
per-URL <lastmod>; the newest page holds the remainder (a few hundred).
Pages are ordered oldest -> newest, so we walk from the highest page number
downwards until a page's newest lastmod is older than the window start.

<lastmod> IS the publication time on this site: on 4 spot checks the JSON-LD
"datePublished" of the article page equalled the sitemap <lastmod> to the
second (2026-09-30T00:10:28Z, 2026-09-30T00:30:23Z, ...), so the listed date
is the date part of <lastmod>. The sitemap mixes raw UTF-8 Persian with
percent-encoded bytes in <loc>, so every path is percent-quoted before use
(existing escapes preserved) - urllib refuses non-ASCII URLs otherwise.

Output: data/urls_custom/donya-e-eqtesad-com.tsv, "URL<TAB>YYYY-MM-DD", unique.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://donya-e-eqtesad.com"
INDEX = BASE + "/sitemap.xml"
OUT = "data/urls_custom/donya-e-eqtesad-com.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MAX_PAGES = 12  # hard stop; the window needs ~5


def page_url(page, per_page=2000):
    raw = json.dumps({"model": "newsstudioPage", "page": page, "perPage": per_page},
                     separators=(",", ":")).encode()
    b64 = base64.b64encode(raw).decode().rstrip("=")
    return f"{BASE}/sitemap/{b64},,.xml"


def quote_url(u):
    return urllib.parse.quote(u.strip(), safe="%/:?&=#~\u200c")


def parse_urlset(text):
    """-> list of (url, lastmod_string)"""
    rows = []
    for blk in re.findall(r"<url>(.*?)</url>", text, re.S):
        m = re.search(r"<loc>(.*?)</loc>", blk, re.S)
        if not m:
            continue
        lm = re.search(r"<lastmod>(.*?)</lastmod>", blk)
        if not lm:
            continue
        rows.append((m.group(1), lm.group(1).strip()))
    return rows


def max_page_from_index():
    status, text, _ = fetch(INDEX)
    print(f"index {INDEX} -> {status}", flush=True)
    if status != 200 or not text:
        return None
    best = None
    for loc in re.findall(r"<loc>(.*?)</loc>", text, re.S):
        loc = loc.strip()
        stem = loc.rsplit("/", 1)[-1]
        stem = stem.split(",,")[0]
        try:
            pad = stem + "=" * (-len(stem) % 4)
            obj = json.loads(base64.urlsafe_b64decode(pad))
        except Exception:
            continue
        if obj.get("model") != "newsstudioPage":
            continue
        try:
            p = int(obj.get("page"))
        except (TypeError, ValueError):
            continue
        if best is None or p > best:
            best = p
    return best


def main():
    found = {}  # url -> date string
    per_day = {}

    top = max_page_from_index()
    if top is None:
        # fallback: binary search the highest page number that still returns urls
        print("index unusable, binary-searching last page", flush=True)
        lo, hi = 1, 3000
        while lo < hi:
            mid = (lo + hi + 1) // 2
            st, tx, _ = fetch(page_url(mid))
            if st == 200 and tx and "<url>" in tx:
                lo = mid
            else:
                hi = mid - 1
        top = lo
        print(f"last page = {top}", flush=True)

    fetched = 0
    page = top
    while page >= 1 and fetched < MAX_PAGES:
        u = page_url(page)
        status, text, _ = fetch(u)
        fetched += 1
        if status != 200 or not text:
            print(f"page {page} -> {status}, stop", flush=True)
            break
        rows = parse_urlset(text)
        if not rows:
            print(f"page {page}: no urls, stop", flush=True)
            break
        dates = sorted(r[1][:10] for r in rows if len(r[1]) >= 10)
        if not dates:
            break
        print(f"page {page}: {len(rows)} urls, {dates[0]} .. {dates[-1]}", flush=True)
        for loc, lm in rows:
            if len(lm) < 10:
                continue
            d = lm[:10]
            try:
                dd = date(*[int(x) for x in d.split("-")])
            except ValueError:
                continue
            if START <= dd <= END:
                url = quote_url(loc)
                if url not in found:
                    found[url] = d
                    per_day[d] = per_day.get(d, 0) + 1
        # stop once the whole page predates the window
        if dates[-1] < START.isoformat():
            break
        page -= 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(found, key=lambda x: (found[x], x)):
            f.write(f"{url}\t{found[url]}\n")

    print(f"pages fetched: {fetched}", flush=True)
    print(f"wrote {len(found)} urls -> {OUT}", flush=True)
    for d in sorted(per_day):
        print(f"  {d}\t{per_day[d]}", flush=True)
    total_days = (END - START).days + 1
    print(f"days covered: {len(per_day)}/{total_days}", flush=True)


if __name__ == "__main__":
    main()
