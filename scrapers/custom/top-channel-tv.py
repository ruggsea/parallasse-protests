#!/usr/bin/env python3
"""top-channel.tv (Top Channel, Albania) — article URLs published 2026-09-25 .. 2026-10-25.

Route: WordPress per-day date archives (https://top-channel.tv/YYYY/MM/DD/ + /page/N/).
The site serves a normal WordPress permalink /YYYY/MM/DD/slug/ = the post's own publish date,
and the day archive lists exactly the posts whose post_date is that day.  Sitemaps, feeds and
the REST API all answer 403/401 to a non-browser client (WAF), while HTML pages answer 200.

Output: data/urls_custom/top-channel-tv.tsv   URL<TAB>YYYY-MM-DD, no header, unique.
Every request goes through scrapers/polite_fetch.py (robots.txt, per-host rate limit, logging).
"""
import sys, re, time
from datetime import date, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = f"{ROOT}/data/urls_custom/top-channel-tv.tsv"
HOST = "https://top-channel.tv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
MAX_PAGES = 40

# /YYYY/MM/DD/slug/  (slug is lowercase ascii; allow %xx and unicode-ish noise defensively)
LINK_RE = re.compile(r'https://top-channel\.tv/(\d{4})/(\d{2})/(\d{2})/([A-Za-z0-9\-_.%]+)/')


def get(url, tries=3):
    """Fetch with a small retry ladder for transient/WAF answers. 404 etc. return immediately."""
    delay = 5
    for attempt in range(tries):
        status, text, _ = fetch(url)
        if status == 200:
            return status, text
        if status in (404, 410, -1):
            return status, None
        if attempt == tries - 1:
            return status, None
        time.sleep(delay)
        delay *= 2
    return status, None


def day_articles(day):
    """All article URLs (with that day's date in the permalink) from the day archive, all pages."""
    key = day.strftime("%Y-%m-%d")
    found = []            # keep discovery order
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        url = f"{HOST}/{day.strftime('%Y/%m/%d')}/" if page == 1 else \
              f"{HOST}/{day.strftime('%Y/%m/%d')}/page/{page}/"
        status, text = get(url)
        if status != 200 or not text:
            break
        matches = [f"{HOST}/{a}/{b}/{c}/{s}/" for a, b, c, s in LINK_RE.findall(text)
                   if f"{a}-{b}-{c}" == key]
        new = [u for u in matches if u not in seen]
        if not new:
            break
        for u in new:
            seen.add(u)
            found.append(u)
    return found


def main():
    rows = {}             # url -> date string
    per_day = {}
    d = START
    while d <= END:
        urls = day_articles(d)
        key = d.isoformat()
        added = 0
        for u in urls:
            if u not in rows:          # unique URLs; first date wins (permalinks carry their own date)
                rows[u] = key
                added += 1
        per_day[key] = added
        print(f"{key}: {added} URLs", flush=True)
        d += timedelta(days=1)

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u in sorted(rows, key=lambda x: (rows[x], x)):
            f.write(f"{u}\t{rows[u]}\n")
    print(f"total {len(rows)} URLs over {len([k for k, v in per_day.items() if v])} days -> {OUT}")
    thin = [k for k in ("2026-09-30", "2026-10-10", "2026-10-20") if per_day.get(k, 0) < 15]
    if thin:
        print("WARNING: fewer than 15 URLs on " + ", ".join(thin))


if __name__ == "__main__":
    main()
