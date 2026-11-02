#!/usr/bin/env python3
"""hamshahrionline.ir (Hamshahri, Iran) - article URLs 2026-09-25 .. 2026-10-25.

Route (found 2026-10-27):
  robots.txt is permissive and lists Sitemap: /sitemap/1405/sitemap.xml (Jalali year 1405).
  That index is a list of PER-DAY files /sitemap/1405/MM/DD/sitemap.xml (Jalali month/day).
  Each day file is served as JSON, not XML:
      {"urls":[{"loc":"https://www.hamshahrionline.ir/news/<id>/<slug>",
                "lastmode":"2026-09-27T19:59:29Z", ...}]}
  "lastmode" (sic) IS the publish instant (Tehran local time labelled Z) and equals the
  article page's JSON-LD "datePublished" to the second (verified on re-fetched samples).
  /sitemap/news/sitemap.xml only holds the last ~100 items (~12h), too short - not used.

  Jalali <-> Gregorian conversion is done here so the 31 window days map to their day files.
  URLs contain raw Persian text; they are percent-encoded before any request, otherwise
  urllib raises and every fetch returns status 0.
"""
import json
import re
import sys
import urllib.parse
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = ROOT + "/data/urls_custom/hamshahrionline-ir.tsv"
HOST = "https://www.hamshahrionline.ir"
START = (2026, 9, 25)
END = (2026, 10, 25)


# ---------- Jalali <-> Gregorian (standard jalaali algorithm) ----------
def _div(a, b):
    return a // b


def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400)
    g_day_no += g_d_m[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + _div(j_day_no, 31)
        jd = 1 + (j_day_no % 31)
    else:
        jm = 7 + _div(j_day_no - 186, 30)
        jd = 1 + ((j_day_no - 186) % 30)
    return jy, jm, jd


import datetime as _dt


def days(start, end):
    d = _dt.date(*start)
    e = _dt.date(*end)
    while d <= e:
        yield d
        d += _dt.timedelta(days=1)


def enc(url):
    """Percent-encode a URL that may carry raw Persian text."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%:@&=+$,~-._")
    query = urllib.parse.quote(parts.query, safe="=&%:@+,~-._/?")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def parse_day(body):
    """Day files come back as JSON; fall back to XML if that ever changes."""
    items = []
    body = body.strip()
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except ValueError:
            return items
        for row in data.get("urls") or []:
            loc = row.get("loc") or row.get("url")
            lm = row.get("lastmode") or row.get("lastmod") or row.get("lastmodd")
            if loc:
                items.append((loc, lm))
        if items:
            return items
    for m in re.finditer(r"<url>(.*?)</url>", body, re.S):
        blk = m.group(1)
        loc = re.search(r"<loc>([^<]+)</loc>", blk)
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", blk)
        if loc:
            items.append((loc.group(1), lm.group(1) if lm else None))
    return items


def main():
    rows = {}
    seen_days = Counter()
    to_fetch = set()
    for d in days(START, END):
        jy, jm, jd = g2j(d.year, d.month, d.day)
        to_fetch.add((d, jy, jm, jd))

    reqs = 0
    for d, jy, jm, jd in sorted(to_fetch):
        url = f"{HOST}/sitemap/{jy}/{jm:02d}/{jd:02d}/sitemap.xml"
        status, body, _ = fetch(url)
        reqs += 1
        if status != 200 or not body:
            print(f"  ! {jy}/{jm:02d}/{jd:02d} ({d}) status {status}", file=sys.stderr)
            continue
        n = 0
        for loc, lm in parse_day(body):
            if not lm:
                continue
            day = lm[:10]
            try:
                y, mo, da = (int(x) for x in day.split("-"))
                if not (_dt.date(*START) <= _dt.date(y, mo, da) <= _dt.date(*END)):
                    continue
            except ValueError:
                continue
            u = enc(loc)
            if not u.startswith("http"):
                continue
            if u in rows:
                continue
            rows[u] = day
            seen_days[day] += 1
            n += 1
        print(f"  {jy}/{jm:02d}/{jd:02d} ({d}): +{n}")

    with open(OUT, "w") as f:
        for u, day in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{u}\t{day}\n")

    print(f"\n{len(rows)} unique URLs written to {OUT} ({reqs} day files fetched)")
    print("per day:")
    for d in days(START, END):
        print(f"  {d}: {seen_days.get(str(d), 0)}")
    for k in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"target {k}: {seen_days.get(k, 0)}")


if __name__ == "__main__":
    main()
