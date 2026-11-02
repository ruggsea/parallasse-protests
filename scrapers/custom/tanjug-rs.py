#!/usr/bin/env python3
"""List tanjug.rs article URLs published 2026-09-25..2026-10-25.

Route: https://www.tanjug.rs/rss (permissive robots, 200) lists ~45 per-section
RSS feeds at /rss/<section>. Each feed returns up to 1000 <item> entries with
<link> and <pubDate> in Serbian local time (+0100/+0200), going back several
weeks (deeper for busy sections). The union of all feeds covers the window.
Listed date = pubDate date (Serbia local time, same as the date shown on the
article page). The /sitemap/news.xml in robots.txt only covers ~2 days, so it
is not used.
"""
import os
import re
import sys
import time
from collections import Counter
from email.utils import parsedate_to_datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.tanjug.rs"
START, END = "2026-09-25", "2026-10-25"
OUT = "data/urls_custom/tanjug-rs.tsv"

FEEDS = [
    "/rss",
    "/rss/beograd",
    "/rss/bliski-istok",
    "/rss/ekonomija",
    "/rss/ekonomija/ekologija",
    "/rss/ekonomija/kompanije",
    "/rss/ekonomija/region",
    "/rss/ekonomija/srbija",
    "/rss/ekonomija/svet",
    "/rss/ekonomija/turizam",
    "/rss/english",
    "/rss/english/economy",
    "/rss/english/politics",
    "/rss/english/society",
    "/rss/english/sports",
    "/rss/eu",
    "/rss/expo-2027",
    "/rss/kultura",
    "/rss/kultura/art",
    "/rss/kultura/film",
    "/rss/kultura/knjige",
    "/rss/kultura/kulturno",
    "/rss/kultura/muzika",
    "/rss/kultura/pozoriste",
    "/rss/kultura/reflektor",
    "/rss/nauka",
    "/rss/novosadski-selfi",
    "/rss/region",
    "/rss/region/drustvo",
    "/rss/region/hronika",
    "/rss/region/politika",
    "/rss/regionalni-puls",
    "/rss/skolski-sport",
    "/rss/sport",
    "/rss/sport/fudbal",
    "/rss/sport/kosarka",
    "/rss/sport/odbojka",
    "/rss/sport/ostali-sportovi",
    "/rss/sport/tenis",
    "/rss/sport/vaterpolo",
    "/rss/srbija",
    "/rss/srbija/drustvo",
    "/rss/srbija/hronika",
    "/rss/srbija/politika",
    "/rss/svet",
    "/rss/svet/drustvo",
    "/rss/svet/hronika",
    "/rss/svet/politika",
    "/rss/tesla-covek-buducnosti",
    "/rss/zanimljivosti",
]

LINK_RE = re.compile(r"<link>\s*([^<\s]+)\s*</link>", re.S)
DATE_RE = re.compile(r"<pubDate>\s*([^<]+?)\s*</pubDate>", re.S)


def norm(url):
    return url.split("#", 1)[0].rstrip("/") + ""


def main():
    urls = {}  # url -> date string
    for path in FEEDS:
        ok = False
        for attempt in range(3):
            try:
                status, text, _ = fetch(BASE + path)
            except Exception as e:
                print(f"  {path}: error {e!r}, retrying", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
                continue
            if status == 200 and text:
                ok = True
                break
            if status in (403, 429, 500, 502, 503, 504):
                time.sleep(10 * (attempt + 1))
                continue
            break
        if not ok:
            print(f"FEED FAILED {path} (last status {status})", file=sys.stderr)
            continue
        links = LINK_RE.findall(text)
        dates = DATE_RE.findall(text)
        pairs = []
        # items are <item>...</item> blocks; parse per block to pair link/date
        for block in re.findall(r"<item>(.*?)</item>", text, re.S):
            lm = LINK_RE.search(block)
            dm = DATE_RE.search(block)
            if not (lm and dm):
                continue
            try:
                dt = parsedate_to_datetime(dm.group(1))
            except Exception:
                continue
            pairs.append((lm.group(1).strip(), dt))
        new = 0
        for link, dt in pairs:
            d = dt.astimezone(dt.tzinfo).date().isoformat()
            if START <= d <= END:
                if link not in urls:
                    urls[link] = d
                    new += 1
        print(f"{path}: {len(pairs)} items, {new} new in window "
              f"(oldest {min((d for _, d in pairs), default='-') if pairs else '-'})",
              file=sys.stderr)
        time.sleep(1)

    per_day = Counter(urls.values())
    total = 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(f"{url}\t{urls[url]}\n")
    print(f"TOTAL {len(urls)} URLs -> {OUT}", file=sys.stderr)
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}", file=sys.stderr)
    missing = [d for d in per_day if per_day[d] < 15]
    print(f"days under 15: {missing if missing else 'none'}", file=sys.stderr)
    # also print per-day counts to stdout (required: "print how many URLs it wrote per day")
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")
    print(f"total\t{len(urls)}")


if __name__ == "__main__":
    main()
