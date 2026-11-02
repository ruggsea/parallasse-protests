#!/usr/bin/env python3
"""decorrespondent.nl (De Correspondent, NL) -> data/urls_custom/decorrespondent-nl.tsv

Route: robots.txt names no Sitemap and no wildcard Disallow (only a long list of
AI bots is disallowed; our UA is not among them). /sitemap.xml and
/sitemap_index.xml answer 404.

What works is the site's own RSS feed:
    https://decorrespondent.nl/feed/v1/publications     (20 items per page)
    .../publications/2, /3, ...                         (atom:link rel="next")
Each <item> has <link> = https://decorrespondent.nl/<id> and <pubDate> in UTC.
31 days = 4 feed pages (~60 items).

Volume: 2-4 pieces per weekday, nothing at weekends (see notes in the json.part).

Dates: <pubDate> is an instant; the site's local day is Europe/Amsterdam. The
article page repeats the same instant in article:published_time and JSON-LD
datePublished (verified identical). We prefer the value read on the page.

Paywall: De Correspondent is members-only. Most article URLs answer 200 but
serve the login page (title "Inloggen - De Correspondent", ~1100 chars of
text). Open-access pieces render the story (~3600+ chars). Only URLs whose page
really renders the article with >= 1500 characters of text are kept, so every
line of the tsv is a readable article carrying its own date.
"""
import html
import re
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

AMS = ZoneInfo("Europe/Amsterdam")
START, END = "2026-09-25", "2026-10-25"
FEED = "https://decorrespondent.nl/feed/v1/publications"
OUT = ROOT / "data/urls_custom/decorrespondent-nl.tsv"
MIN_TEXT = 1500


def text_of(body):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))


def page_date(body):
    for pat in (r'article:published_time"\s+content="([^"]+)"',
                r'"datePublished"\s*:\s*"([^"]+)"'):
        m = re.search(pat, body)
        if m:
            try:
                dt = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                return dt.astimezone(AMS).date().isoformat()
            except ValueError:
                pass
    return None


def slow_fetch(url, tries=3):
    """polite_fetch with an extra back-off: the site 429s a fast client."""
    for attempt in range(tries):
        status, body, _ = fetch(url)
        if status == 200:
            time.sleep(4)
            return status, body
        if status in (429, 503, 502, 500, 504):
            wait = 30 * (attempt + 1)
            print(f"{url}\tstatus {status}, sleep {wait}s")
            time.sleep(wait)
            continue
        time.sleep(4)
        return status, body
    return status, body


def feed_items(max_pages=10):
    items, page = [], 0
    while page < max_pages:
        url = FEED if page == 0 else f"{FEED}/{page + 1}"
        status, body = slow_fetch(url)
        page += 1
        if status != 200 or not body:
            print(f"feed page {page}: status {status}, stop")
            break
        found = re.findall(r"<item>(.*?)</item>", body, re.S)
        if not found:
            break
        for it in found:
            link = re.search(r"<link>([^<]+)</link>", it)
            pub = re.search(r"<pubDate>([^<]+)</pubDate>", it)
            if not link or not pub:
                continue
            dt = parsedate_to_datetime(pub.group(1))
            items.append((link.group(1).split("?")[0],
                          dt.astimezone(AMS).date().isoformat()))
        oldest = min(d for _, d in items)
        print(f"feed page {page}: {len(found)} items, oldest {oldest}")
        if oldest < START:
            break
    return items


def main():
    items = feed_items()
    win = [(u, d) for u, d in dict.fromkeys(items) if START <= d <= END]
    print(f"in window: {len(win)} urls")
    rows, locked = [], 0
    for url, feed_day in win:
        status, body = slow_fetch(url)
        if status != 200 or not body:
            print(f"{url}\tstatus {status}")
            continue
        txt = text_of(body)
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        title = title.group(1).strip() if title else ""
        if len(txt) < MIN_TEXT or title.startswith("Inloggen"):
            locked += 1
            print(f"{url}\tlocked ({len(txt)} chars)")
            continue
        day = page_date(body) or feed_day
        rows.append((url, day))
        print(f"{url}\t{day}\t{len(txt)} chars\t{title[:70]}")
    seen, final = set(), []
    for url, day in sorted(rows, key=lambda r: (r[1], r[0])):
        if url not in seen and START <= day <= END:
            seen.add(url)
            final.append((url, day))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for url, day in final:
            f.write(f"{url}\t{day}\n")
    print(f"\nopen: {len(final)}  locked: {locked}  -> {OUT}")
    per_day = {}
    for _, day in final:
        per_day[day] = per_day.get(day, 0) + 1
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")


if __name__ == "__main__":
    main()
