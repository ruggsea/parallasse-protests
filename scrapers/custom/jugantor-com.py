#!/usr/bin/env python3
"""jugantor.com (Bangladesh) -- article URLs for 2026-09-25..2026-10-25.

Route (see grids/custom/out/jugantor-com.json.part):
  robots.txt is permissive (Allow: /, only /ajax/ disallowed).
  /sitemap.xml index holds only static pages + sections + /news_sitemap.xml
  (that one is a 500-entry Google-News sitemap covering ~2 days, so it cannot
  reach back to 09-25).  Per-day files /sitemap/sitemap-YYYY-MM-DD.xml exist but
  return an EMPTY urlset for every date (soft 404), and there is no RSS/feed.
  The site's own archive has a PRINT view:
      /archive/print?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD
  which lists every newspaper article of that day (one request = ~180 links,
  no pagination) -- that is the primary route.  The paginated
  /archive?search=yes&dateFrom=..&dateTo=..&page=N is the fallback.
Date = the archive day the site filtered on (== page JSON-LD datePublished,
2026-10-10T00:00:00+06:00 on the samples checked).
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.jugantor.com"
OUT = Path("data/urls_custom/jugantor-com.tsv")
START, END = "2026-09-25", "2026-10-25"

ART = re.compile(r'href="(?:' + re.escape(BASE) + r')?(/[A-Za-z0-9\-]+/\d{6,})"')


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as e:  # noqa: BLE001
            status, text = 0, str(e)
        if status == 200 and text:
            return text
        if status == -1:  # robots disallow
            return None
        time.sleep(2 + 2 * i)
    return None


def parse(text):
    """Return article paths in page order, de-duplicated."""
    seen, res = set(), []
    for m in ART.finditer(text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        res.append(p)
    return res


def days(start, end):
    import datetime as dt
    d = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += dt.timedelta(days=1)


def day_urls(day):
    """All article paths the archive says were published on `day`."""
    paths = []
    txt = get(f"{BASE}/archive/print?dateFrom={day}&dateTo={day}")
    if txt:
        paths = parse(txt)
    if len(paths) < 15:  # fallback: paginated archive listing
        for page in range(1, 41):
            t = get(f"{BASE}/archive?search=yes&dateFrom={day}&dateTo={day}&page={page}")
            if not t:
                break
            got = parse(t)
            new = [p for p in got if p not in paths]
            paths.extend(new)
            if not new or 'rel="next"' not in t:
                break
    return paths


def news_sitemap_days():
    """Supplement from the Google-News sitemap (only covers the last ~2 days)."""
    extra = {}
    txt = get(f"{BASE}/news_sitemap.xml")
    if not txt:
        return extra
    for block in re.findall(r"(?s)<url>(.*?)</url>", txt):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        pub = re.search(r"<news:publication_date>(.*?)</news:publication_date>", block)
        if not loc or not pub:
            continue
        day = pub.group(1)[:10]
        if START <= day <= END:
            u = loc.group(1).strip()
            m = re.match(re.escape(BASE) + r"(/[A-Za-z0-9\-]+/\d{6,})", u)
            if m:
                extra.setdefault(day, []).append(m.group(1))
    return extra


def main():
    rows, seen = [], set()
    per_day = {}
    for day in days(START, END):
        got = 0
        for p in day_urls(day):
            u = BASE + p
            if u in seen:
                continue
            seen.add(u)
            rows.append((u, day))
            got += 1
        per_day[day] = got
        print(f"{day}\t{got}", flush=True)

    for day, paths in news_sitemap_days().items():
        for p in paths:
            u = BASE + p
            if u in seen:
                continue
            seen.add(u)
            rows.append((u, day))
            per_day[day] = per_day.get(day, 0) + 1

    rows.sort(key=lambda r: (r[1], r[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tsv.tmp")
    with open(tmp, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")
    tmp.replace(OUT)
    print(f"TOTAL {len(rows)} URLs -> {OUT}")
    print("per-day: " + ", ".join(f"{d}={n}" for d, n in sorted(per_day.items()) if n))
    low = [d for d, n in sorted(per_day.items()) if n < 15]
    print("days with <15: " + (", ".join(low) if low else "none"))


if __name__ == "__main__":
    main()
