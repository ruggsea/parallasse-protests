#!/usr/bin/env python3
"""Meduza (meduza.io) article URL lister for a fixed date window.

Route (worked out 2026-10-27):
  meduza.io/robots.txt is permissive (only /insite/ and /embed/ disallowed) and names
  no sitemap; /sitemap.xml answers 502, /sitemap/news.xml and /sitemap/index.xml 403,
  /rss 502, /rss/news only 30 items (~1.5 days). The site's own single-page app calls a
  JSON search endpoint whose path is built in /app.<hash>.js as
      /api/w5/${searchRoute}?chrono=&page=&per_page=&locale=
  with window.searchRoute = "new_search" (set inline in every page's HTML):
      /api/w5/new_search?chrono=news&page=N&per_page=100&locale=ru   -> 200, JSON
  It returns {"_count", "collection" (document keys), "documents" {key: {"datetime":unix,
  "url":key, "title", ...}}, "has_next"}, sorted newest first, mixing news/, feature/,
  short/, slides/, video/, episodes/. Publication date = the document's own `datetime`
  converted to Europe/Moscow (UTC+3, no DST), which is the date the site itself puts in
  the /YYYY/MM/DD/ path segment.
"""
import datetime as dt
import json
import os
import sys
import time

ROOT = "."
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

API = "https://meduza.io/api/w5/new_search?chrono={c}&page={p}&per_page=100&locale=ru"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
MSK = dt.timezone(dt.timedelta(hours=3))
OUT = os.path.join(ROOT, "data/urls_custom/meduza-io.tsv")
CHRONOS = ("news", "articles")
MAX_PAGES_PER_CHRONO = 15
# keep only kinds that carry real article prose (galleries/video/podcasts do not)
KEEP = ("news/", "feature/")

req = 0


def get(url, tries=2):
    global req
    for i in range(tries):
        req += 1
        status, text, _ = fetch(url)
        if status == 200 and text:
            return status, text
        if status in (0, 429, 502, 503) and i + 1 < tries:
            time.sleep(5 + 5 * i)
            continue
        return status, text
    return status, text


def main():
    rows = {}          # url -> date
    seen_days = {}     # date -> count
    dropped = {}       # prefix -> count inside window (for the notes)
    per_day_all = {}   # date -> count of all kinds in window
    for chrono in CHRONOS:
        for page in range(MAX_PAGES_PER_CHRONO):
            status, text = get(API.format(c=chrono, p=page))
            if status != 200 or not text:
                print(f"# {chrono} page {page}: HTTP {status}, stopping this chrono",
                      file=sys.stderr)
                break
            try:
                j = json.loads(text)
            except ValueError:
                print(f"# {chrono} page {page}: not JSON", file=sys.stderr)
                break
            docs = j.get("documents") or {}
            if not docs:
                break
            oldest = None
            for key, d in docs.items():
                ts = d.get("datetime")
                if not ts:
                    continue
                day = dt.datetime.fromtimestamp(ts, MSK).date()
                if oldest is None or day < oldest:
                    oldest = day
                if day < START or day > END:
                    continue
                url_key = d.get("url") or key
                pref = url_key.split("/")[0] + "/"
                per_day_all[day] = per_day_all.get(day, 0) + 1
                if pref not in KEEP:
                    dropped[pref] = dropped.get(pref, 0) + 1
                    continue
                rows["https://meduza.io/" + url_key] = day
            if oldest is not None and oldest < START:
                break
            if not j.get("has_next"):
                break
        else:
            print(f"# {chrono}: hit page cap {MAX_PAGES_PER_CHRONO}", file=sys.stderr)

    for day in rows.values():
        seen_days[day] = seen_days.get(day, 0) + 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for url, day in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{url}\t{day.isoformat()}\n")
    os.replace(tmp, OUT)

    print(f"total unique URLs {len(rows)}, requests {req}")
    d = START
    while d <= END:
        print(f"{d.isoformat()}\t{seen_days.get(d,0)}\tof\t{per_day_all.get(d,0)}")
        d += dt.timedelta(days=1)
    print("dropped kinds:", dict(sorted(dropped.items())), file=sys.stderr)


if __name__ == "__main__":
    main()
