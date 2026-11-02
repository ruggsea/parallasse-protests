#!/usr/bin/env python3
"""makfax.com.mk (North Macedonia) - article URLs published 2026-09-25 .. 2026-10-25.

Route: WordPress (MVP theme) day archives  https://makfax.com.mk/YYYY/MM/DD/  and their
pagination  https://makfax.com.mk/YYYY/MM/DD/page/N/  (20 items per page, the page title
states "Page k of M").  The listed date is the day of the archive URL (site-local Skopje
date), which is the same day the article page prints in <time datetime> / and in
article:published_time rendered in local time.

robots.txt (2026-10-27) is permissive ("User-agent: * / Disallow:") and names
/sitemap.xml, but the post sitemaps carry edit-time <lastmod> (a 2017 article lists
2026-10-22), so they are not usable as publication dates.  /wp-json/wp/v2/posts answers
401, /wp-sitemap.xml is an empty <urlset>.

Every request goes through polite_fetch.fetch (robots.txt, 1-2 req/s per host, logged).
"""
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://makfax.com.mk"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT = Path("data/urls_custom/makfax-com-mk.tsv")

MONTHS = [
    "јануари", "февруари", "март", "април", "мај", "јуни",
    "јули", "август", "септември", "октомври", "ноември", "декември",
]

ITEM_RE = re.compile(r'<li class="mvp-blog-story-wrap[^"]*">\s*<a href="(https://makfax\.com\.mk/[^"]+)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
PAGES_RE = re.compile(r"page\s+\d+\s+of\s+(\d+)", re.I)
MAX_PAGES = 12          # 20 items/page -> at most 240 articles per day
TIMEOUT_BUDGET = 60 * 18  # seconds; stay well under 20 minutes


def title_of(html):
    m = TITLE_RE.search(html)
    return m.group(1) if m else ""


def items_of(html):
    return ITEM_RE.findall(html)


def main():
    started = datetime.datetime.now()
    day_to_urls = {}
    d = START
    requests = 0
    while d <= END:
        if (datetime.datetime.now() - started).total_seconds() > TIMEOUT_BUDGET:
            print("time budget reached, stopping early at", d)
            break
        day_url = "{}/{:%Y/%m/%d}/".format(BASE, d)
        expect = "{} {}, {}".format(d.day, MONTHS[d.month - 1], d.year).lower()
        status, html, _ = fetch(day_url)
        requests += 1
        urls = []
        pages_done = 0
        total_pages = 1
        if status == 200 and html:
            ttl = title_of(html).lower()
            if expect in ttl:
                urls.extend(items_of(html))
                pages_done = 1
                m = PAGES_RE.search(ttl)
                if m:
                    total_pages = int(m.group(1))
        else:
            print("  {} -> status {}".format(day_url, status))
        # page 1 carries no "Page k of M" hint; page 2 does, so probe it and then walk
        p = 2
        while pages_done and p <= MAX_PAGES:
            if (datetime.datetime.now() - started).total_seconds() > TIMEOUT_BUDGET:
                break
            purl = "{}page/{}/".format(day_url, p)
            st, phtml, _ = fetch(purl)
            requests += 1
            if st != 200 or not phtml:
                break
            ttl = title_of(phtml).lower()
            if expect not in ttl:
                break
            m = PAGES_RE.search(ttl)
            if m:
                total_pages = int(m.group(1))
            got = items_of(phtml)
            if not got:
                break
            urls.extend(got)
            pages_done += 1
            if p >= total_pages:
                break
            p += 1
        day_to_urls[d.isoformat()] = urls
        print("{}\t{} urls ({} of {} page(s)){}".format(
            d.isoformat(), len(urls), pages_done, total_pages,
            " TRUNCATED" if pages_done < total_pages else ""))
        d += datetime.timedelta(days=1)

    # dedupe: first day seen wins, keep insertion order
    seen = {}
    for day in sorted(day_to_urls):
        for u in day_to_urls[day]:
            u = u.split("#")[0]
            if u not in seen:
                seen[u] = day

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [u + "\t" + day for u, day in
             sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))]
    OUT.write_text("".join(l + "\n" for l in lines))

    per_day = {}
    for u, day in seen.items():
        per_day[day] = per_day.get(day, 0) + 1
    print("--- wrote {} urls to {} ({} requests)".format(len(seen), OUT, requests))
    for day in sorted(per_day):
        print("{}\t{}".format(day, per_day[day]))
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("target {}: {} urls".format(target, per_day.get(target, 0)))


if __name__ == "__main__":
    main()
