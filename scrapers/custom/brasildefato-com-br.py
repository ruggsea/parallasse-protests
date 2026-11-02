#!/usr/bin/env python3
"""Brasil de Fato (brasildefato.com.br) — article URLs for 2026-09-25..2026-10-25.

Route: the site is WordPress and its REST API is open (robots.txt only disallows
/wp-admin/ and /search/).  /wp-json/wp/v2/posts?after=..&before=..&per_page=100
returns 100 posts per page, newest first, each with `date` (site-local, UTC-3)
and `link` (/YYYY/MM/DD/slug/).  Paginate until the window is exhausted.

Fallback (only if the API stops answering): /sitemap.xml is a flat <urlset>;
keep article URLs matching /YYYY/MM/DD/ whose lastmod falls in the window and
take the date from the URL path.

Writes data/urls_custom/brasildefato-com-br.tsv as "URL<TAB>YYYY-MM-DD".
"""
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/brasildefato-com-br.tsv")
HOST = "https://www.brasildefato.com.br"
START = date(2026, 9, 25)
END = date(2026, 10, 25)          # inclusive
WINDOW_DAYS = [(START + timedelta(days=i)) for i in range((END - START).days + 1)]
ART = re.compile(r"^https?://(?:www\.)?brasildefato\.com\.br/(20\d\d)/(\d\d)/(\d\d)/[^/?#]+/?$")


def in_window(d):
    return START <= d <= END


def api_page(page, per_page=100):
    url = (f"{HOST}/wp-json/wp/v2/posts?per_page={per_page}&page={page}"
           f"&after={START.isoformat()}T00:00:00&before={(END + timedelta(days=1)).isoformat()}T00:00:00"
           f"&orderby=date&order=desc&_fields=date,link,type")
    for attempt in range(3):
        try:
            status, text, _ = fetch(url)
        except Exception as e:                                    # network hiccup
            print(f"  page {page} attempt {attempt+1}: exception {e}", file=sys.stderr)
            status, text = 0, None
        if status == 200 and text:
            try:
                return json.loads(text)
            except ValueError:
                print(f"  page {page} attempt {attempt+1}: bad JSON", file=sys.stderr)
        else:
            print(f"  page {page} attempt {attempt+1}: HTTP {status}", file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    return None


def via_api(rows):
    """rows: OrderedDict url -> date string. Returns True if the window was covered."""
    page, per_page = 1, 100
    empty_streak = 0
    while page <= 80:
        data = api_page(page, per_page)
        if data is None:
            print(f"  API gave up at page {page}", file=sys.stderr)
            return False
        if not data:
            break
        added = 0
        for it in data:
            link = (it.get("link") or "").strip()
            raw = (it.get("date") or "").strip()
            if not link or not raw:
                continue
            try:
                d = datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if not in_window(d):
                continue
            if link not in rows:
                rows[link] = d.isoformat()
                added += 1
        print(f"  API page {page}: {len(data)} items, {added} new", file=sys.stderr)
        if len(data) < per_page:
            break
        empty_streak = empty_streak + 1 if added == 0 else 0
        if empty_streak >= 4:
            break
        page += 1
    return True


def via_day_archives(rows, days):
    """Fallback: /YYYY/MM/DD/ archive pages (server-rendered, carry the day's
    article slugs); the date is the archive day, which is also the URL path date.
    Cross-checked 2026-10-11: the archive lists exactly the 12 posts the API gives."""
    added = 0
    for d in days:
        url = f"{HOST}/{d.year:04d}/{d.month:02d}/{d.day:02d}/"
        try:
            status, text, _ = fetch(url)
        except Exception:
            continue
        if status != 200 or not text:
            print(f"  archive {url}: HTTP {status}", file=sys.stderr)
            continue
        prefix = f"/{d.year:04d}/{d.month:02d}/{d.day:02d}/"
        slugs = set(re.findall(re.escape(prefix) + r"([a-z0-9][a-z0-9\-]{8,})", text))
        for s in slugs:
            link = f"{HOST}{prefix}{s}/"
            if link not in rows:
                rows[link] = d.isoformat()
                added += 1
        print(f"  archive {d.isoformat()}: {len(slugs)} slugs, {added} added so far", file=sys.stderr)
    return added


def via_sitemaps(rows):
    """Fallback: /sitemap.xml flat urlset, date taken from the URL path."""
    seen = set()
    queue = [f"{HOST}/sitemap.xml", f"{HOST}/sitemap.xml?lang=en",
             f"{HOST}/wp-sitemap.xml", f"{HOST}/sitemap_index.xml"]
    while queue:
        u = queue.pop(0)
        if u in seen or len(seen) > 200:
            continue
        seen.add(u)
        try:
            status, text, _ = fetch(u)
        except Exception:
            continue
        if status != 200 or not text:
            print(f"  sitemap {u}: HTTP {status}", file=sys.stderr)
            continue
        # recurse into sitemap indexes
        if "<sitemapindex" in text:
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text):
                if loc not in seen:
                    queue.append(loc)
            continue
        for m in re.finditer(r"<url>(.*?)</url>", text, re.S):
            block = m.group(1)
            lm = re.search(r"<lastmod>\s*([0-9T:\-+.Z]+)\s*</lastmod>", block)
            loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
            if not loc:
                continue
            link = loc.group(1)
            am = ART.match(link)
            if not am:
                continue
            try:
                d = date(int(am.group(1)), int(am.group(2)), int(am.group(3)))
            except ValueError:
                continue
            if not in_window(d):
                continue
            if lm:
                try:
                    lmd = datetime.strptime(lm.group(1)[:10], "%Y-%m-%d").date()
                except ValueError:
                    lmd = d
                # lastmod is the modification time: accept it only inside the window
                if not in_window(lmd):
                    continue
            if link not in rows:
                rows[link] = d.isoformat()
    return bool(rows)


def main():
    t0 = time.time()
    rows = OrderedDict()
    ok = via_api(rows)
    counts = Counter(rows.values())
    thin = [d for d in WINDOW_DAYS if counts.get(d.isoformat(), 0) < 15]
    if not ok or thin:
        print(f"  filling: API ok={ok}, thin days={len(thin)}", file=sys.stderr)
        via_day_archives(rows, thin or WINDOW_DAYS)
        counts = Counter(rows.values())
        still = [d for d in WINDOW_DAYS if counts.get(d.isoformat(), 0) < 15]
        if not ok or len(still) > 3:
            via_sitemaps(rows)
            counts = Counter(rows.values())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for url, d in rows.items():
            f.write(f"{url}\t{d}\n")
    os.replace(tmp, OUT)

    print(f"wrote {len(rows)} unique URLs to {OUT} in {time.time()-t0:.0f}s")
    for d in WINDOW_DAYS:
        print(f"  {d.isoformat()}\t{counts.get(d.isoformat(), 0)}")
    missing = [d.isoformat() for d in WINDOW_DAYS if counts.get(d.isoformat(), 0) == 0]
    print(f"days with 0 URLs: {missing if missing else 'none'}")


if __name__ == "__main__":
    main()
