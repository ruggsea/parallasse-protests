#!/usr/bin/env python3
"""List in.gr article URLs published 2026-09-25 .. 2026-10-25 (inclusive).

Route: WordPress REST API /wp-json/wp/v2/posts.
  - robots.txt is permissive (no Disallow for /wp-json; it only names sitemaps, and
    /sitemap_index.xml and /sitemaps/post-sitemap.xml 404; /sitemap.xml is the homepage HTML;
    /wp-content/uploads/json/sitemap-news.xml is a Google News feed with only ~100 URLs over
    the last ~2 days). So REST is the only route covering the whole window.
  - The WAF caps per_page at 30 (per_page>=35 answers 403) and can answer a transient 400 on a
    single deep page; the script retries each page a few times with growing backoff.
  - REST 'date' is the Athens-local publish time; the article URL path /YYYY/MM/DD/... carries
    the same local date. Listed date = the date in the URL path (mismatches vs REST 'date' are
    counted and reported; a missing URL date falls back to REST 'date').
  - Sweep newest-first, stop when a whole page is older than the window start. Then any day in
    the window with <15 URLs gets a targeted per-day after/before pass as backfill.
"""
import json, os, re, sys, time
from datetime import date, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://www.in.gr/wp-json/wp/v2/posts"
OUT = "data/urls_custom/in-gr.tsv"
START, END = "2026-09-25", "2026-10-25"
PER = 30
DATE_IN_URL = re.compile(r"in\.gr/(\d{4})/(\d{2})/(\d{2})/")


def get_json(url, tries=5):
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            try:
                return json.loads(text)
            except ValueError:
                pass
        time.sleep(20 * (i + 1))
    return None


def sweep():
    found = {}
    mism = 0
    no_date = 0
    page = 1
    while True:
        url = "%s?per_page=%d&_fields=date,link&page=%d" % (BASE, PER, page)
        d = get_json(url)
        if d is None:
            print("page %d failed after retries; stopping sweep" % page)
            break
        if not d:
            break
        for it in d:
            link = it["link"].split("?")[0].split("#")[0]
            rest_date = it["date"][:10]
            m = DATE_IN_URL.search(link)
            url_date = "%s-%s-%s" % m.groups() if m else None
            if m and url_date != rest_date:
                mism += 1
            if url_date is None:
                no_date += 1
                url_date = rest_date
            if START <= url_date <= END:
                found.setdefault(link, url_date)
        oldest = d[-1]["date"][:10]
        print("page %d oldest %s collected %d" % (page, oldest, len(found)))
        if oldest < START or len(d) < PER:
            break
        page += 1
    return found, mism, no_date


def backfill(found):
    per_day = {}
    for dt in found.values():
        per_day[dt] = per_day.get(dt, 0) + 1
    d0, d1 = date.fromisoformat(START), date.fromisoformat(END)
    day = d0
    while day <= d1:
        ds = day.isoformat()
        if per_day.get(ds, 0) < 15:
            bp = (day + timedelta(days=1)).isoformat()
            pg = 1
            added = 0
            while True:
                url = ("%s?per_page=%d&_fields=date,link&after=%sT00:00:00"
                       "&before=%sT00:00:00&page=%d") % (BASE, PER, ds, bp, pg)
                d = get_json(url)
                if d is None:
                    break
                if not d:
                    break
                for it in d:
                    link = it["link"].split("?")[0].split("#")[0]
                    m = DATE_IN_URL.search(link)
                    ud = ("%s-%s-%s" % m.groups()) if m else it["date"][:10]
                    if ud == ds:
                        if link not in found:
                            added += 1
                        found.setdefault(link, ud)
                if len(d) < PER:
                    break
                pg += 1
            per_day[ds] = sum(1 for dt in found.values() if dt == ds)
            print("backfill %s: +%d (total %d)" % (ds, added, per_day[ds]))
        day += timedelta(days=1)
    return per_day


def main():
    found, mism, no_date = sweep()
    print("sweep done: %d urls, url/REST-date mismatches %d, no-url-date %d"
          % (len(found), mism, no_date))
    per_day = backfill(found)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for link in sorted(found):
            f.write("%s\t%s\n" % (link, found[link]))
    print("wrote %d urls to %s" % (len(found), OUT))
    for ds in sorted(per_day):
        print(ds, per_day[ds])
    low = [ds for ds in sorted(per_day) if per_day[ds] < 15]
    print("days under 15:", low if low else "none")


if __name__ == "__main__":
    main()
