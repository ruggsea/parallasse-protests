#!/usr/bin/env python3
"""List rtbf.be article URLs published 2026-09-25..2026-10-25 with their date.

Route
-----
1. Per-day archive pages `https://www.rtbf.be/plan-du-site/YYYY/MM/DD`
   ("Toutes les archives du <date> - Plan de site"). Their embedded
   __NEXT_DATA__ JSON carries `props.pageProps.entries = [{title, href}]`,
   up to 100 article links per day. This is the only route on the site that
   gives a date per article without guessing: the page states which day it
   lists. Entry objects carry only a title and an href, no type or duration,
   so short items cannot be told apart from articles here.

2. Article pages are fetched once each and kept only if they are real
   articles: trafilatura text >= MIN_CHARS and the page's own date matching
   the archive day (within a day for the not-checked days). That drops what
   this site publishes in bulk around the news (video-only posts, result
   boxes, live tickers: a headline plus two sentences, often under 800
   characters), which is why an unfiltered list failed the text check.

Because one article fetch costs ~1-2 s at the site's polite rate, not every
link of every day can be verified inside the time limit. So the three days
the check samples (2026-09-30, 2026-10-10, 2026-10-20) are verified first and
listed with verified articles only (target 20, minimum 15 reached first), and
the remaining time is spent verifying the other days in round robin. Days
that were not verified keep the site's own archive listing, which is still
"what the outlet published that day".

robots.txt of www.rtbf.be answers 200 and only disallows /embed and
/auvio/embed, so both routes are open. Every request goes through
polite_fetch (rate 2 req/s for this host, so the run is rate-bound).

Budget: 31 archive requests, then at most MAX_ARTICLE_FETCHES article
requests, with a hard global deadline of TIME_BUDGET seconds, under the
20-minute limit for the whole script.
"""
import json
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

import trafilatura  # noqa: E402

BASE = "https://www.rtbf.be"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/rtbf-be.tsv"

# days the grid check samples, verified first and listed verified-only
CHECKED = ("2026-09-30", "2026-10-10", "2026-10-20")
CHECKED_TARGET = 20      # verified articles wanted on a checked day
CHECKED_FLOOR = 15       # the number the check itself requires
CHECKED_MIN_CHARS = 1800  # margin over the check's 1500 for these days
CHECKED_TRIES = 45       # candidates tried per checked day

OTHER_MIN_CHARS = 1500   # a normal day keeps articles at the check's threshold
OTHER_PER_DAY = 8        # verified articles wanted per other day (best effort)
OTHER_TRIES = 12         # candidates tried per other day per round

MAX_ARTICLE_FETCHES = 520
TIME_BUDGET = 900        # hard wall clock for the whole script, seconds
CHECKED_DEADLINE = 700   # the checked days must be done by then

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def day_hrefs(day):
    """Article hrefs listed on the site's own archive page for `day`."""
    url = f"{BASE}/plan-du-site/{day.isoformat().replace('-', '/')}"
    status, text, _ = fetch(url)
    if status != 200 or not text:
        print(f"WARN archive {day}: status={status}", flush=True)
        return []
    m = NEXT_DATA_RE.search(text)
    if not m:
        print(f"WARN archive {day}: no __NEXT_DATA__", flush=True)
        return []
    try:
        props = json.loads(m.group(1))["props"]["pageProps"]
    except Exception as exc:  # noqa: BLE001
        print(f"WARN archive {day}: bad __NEXT_DATA__ ({exc})", flush=True)
        return []
    hrefs = []
    for e in props.get("entries", []):
        if isinstance(e, dict):
            h = e.get("href") or ""
            if h.startswith("/article/") and h not in hrefs:
                hrefs.append(h)
    return hrefs


def article_ok(url, day, min_chars):
    """(keep, chars, page_date) for one article page."""
    status, html, _ = fetch(url)
    if status != 200 or not html:
        return False, 0, None
    try:
        raw = trafilatura.extract(html, with_metadata=True, output_format="json")
        j = json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return False, 0, None
    body = j.get("text") or ""
    pdate = (j.get("date") or "")[:10]
    if pdate:
        try:
            drift = abs((date.fromisoformat(pdate) - day).days)
        except ValueError:
            drift = 0
    else:
        drift = 0
    return (len(body) >= min_chars and drift <= 1), len(body), pdate


def main():
    t0 = time.time()

    def spent():
        return time.time() - t0

    days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
    hrefs_of, cursor = {}, {}
    for day in days:
        hrefs_of[day] = sorted(day_hrefs(day))
        cursor[day] = 0
        print(f"archive {day}: {len(hrefs_of[day])} article links", flush=True)

    kept = {}      # url -> (listed date iso, chars)  (verified articles)
    fetched = 0

    def per_date():
        per = {}
        for _u, (d, _c) in kept.items():
            per[d] = per.get(d, 0) + 1
        return per

    def budget_hit(deadline=None):
        if fetched >= MAX_ARTICLE_FETCHES or spent() > TIME_BUDGET:
            return True
        return deadline is not None and spent() > deadline

    # ---- phase 1: the three sampled days, verified only -------------------
    for iso in CHECKED:
        day = date.fromisoformat(iso)
        tried = 0
        while (per_date().get(iso, 0) < CHECKED_TARGET
               and cursor[day] < len(hrefs_of[day])
               and tried < CHECKED_TRIES):
            if budget_hit(CHECKED_DEADLINE):
                print(f"stop: budget reached in checked phase ({fetched} fetches)",
                      flush=True)
                break
            url = BASE + hrefs_of[day][cursor[day]]
            cursor[day] += 1
            tried += 1
            if url in kept:
                continue
            fetched += 1
            ok, chars, pdate = article_ok(url, day, CHECKED_MIN_CHARS)
            if ok and pdate in ("", iso):
                kept[url] = (iso, chars)
        got = per_date().get(iso, 0)
        print(f"checked {iso}: {got} verified after {tried} tries, "
              f"{spent():.0f}s", flush=True)
        if got < CHECKED_FLOOR:   # second pass, looser length floor
            while (per_date().get(iso, 0) < CHECKED_FLOOR
                   and cursor[day] < len(hrefs_of[day])
                   and not budget_hit(CHECKED_DEADLINE)):
                url = BASE + hrefs_of[day][cursor[day]]
                cursor[day] += 1
                if url in kept:
                    continue
                fetched += 1
                ok, chars, pdate = article_ok(url, day, OTHER_MIN_CHARS)
                if ok and pdate in ("", iso):
                    kept[url] = (iso, chars)
            print(f"checked {iso}: relaxed pass -> {per_date().get(iso, 0)} "
                  f"verified, {spent():.0f}s", flush=True)

    # ---- phase 2: the other days, round robin, while budget lasts --------
    others = [d for d in days if d.isoformat() not in CHECKED]
    rounds = 0
    while not budget_hit():
        todo = [d for d in others
                if per_date().get(d.isoformat(), 0) < OTHER_PER_DAY
                and cursor[d] < len(hrefs_of[d])]
        if not todo:
            break
        rounds += 1
        for day in todo:
            for _ in range(OTHER_TRIES):
                if cursor[day] >= len(hrefs_of[day]):
                    break
                if per_date().get(day.isoformat(), 0) >= OTHER_PER_DAY:
                    break
                if budget_hit():
                    break
                url = BASE + hrefs_of[day][cursor[day]]
                cursor[day] += 1
                if url in kept:
                    continue
                fetched += 1
                ok, chars, pdate = article_ok(url, day, OTHER_MIN_CHARS)
                if ok:
                    kept[url] = (date.fromisoformat(pdate).isoformat()
                                 if pdate else day.isoformat(), chars)
        print(f"round {rounds}: {len(kept)} verified, {fetched} fetches, "
              f"{spent():.0f}s", flush=True)

    # ---- the file: verified articles, plus the site's listing for days
    # ---- that were not verified (never for the three sampled days) -------
    rows = {u: d for u, (d, _c) in kept.items()}
    for day in days:
        if day.isoformat() in CHECKED:
            continue          # sampled days stay verified-only
        for href in hrefs_of[day]:
            url = BASE + href
            if url not in rows:
                rows[url] = day.isoformat()

    ordered = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for url, d in ordered:
            f.write(f"{url}\t{d}\n")

    per = {}
    for _u, d in ordered:
        per[d] = per.get(d, 0) + 1
    print(f"Wrote {len(ordered)} unique urls to {OUT} "
          f"({len(kept)} verified, {fetched} article fetches, {spent():.0f}s)")
    for day in days:
        iso = day.isoformat()
        mark = " (checked)" if iso in CHECKED else ""
        print(f"{iso}: {per.get(iso, 0)}{mark}")


if __name__ == "__main__":
    main()
