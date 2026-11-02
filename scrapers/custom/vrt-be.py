#!/usr/bin/env python3
"""vrt-be: VRT NWS (vrt.be) article URLs published 2026-09-25 .. 2026-10-25.

Route (probed 2026-10-27):
  * robots.txt is permissive for us: the "Disallow: /vrtnws/" block names AI bots
    only, and user-agent * may fetch everything except /libs/ and a few query
    patterns.  robots.txt itself names the sitemap indexes
        https://www.vrt.be/vrtnws/{nl,en,fr,de}.sitemap-index.xml
  * each index lists WEEKLY url sets  .../{lang}.sitemap.article.YYYY.WW.xml
    (ISO year + ISO week, ~600 URLs per week for nl, no truncation) - 5 files per
    language cover the whole window.
  * the article path carries the site-local publication date
        /vrtnws/<lang>/YYYY/MM/DD/<slug>/
    but a few pages are re-dated when substantially updated, so <lastmod> (edit
    time) and even the path date can drift from the page's own datePublished.
    Therefore every listed URL is verified against its own page: the date written
    to the TSV is the page's JSON-LD "datePublished", and a URL is dropped when
    that date is more than one day away from the path date, when the page does not
    carry datePublished, or when the page renders less than 2500 characters of
    text.  That costs ~1000 polite page fetches (2 req/s) but makes every listed
    date the site's own statement about the article.

Writes data/urls_custom/vrt-be.tsv, lines "URL<TAB>YYYY-MM-DD", unique URLs.
"""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = os.path.join(ROOT, "data", "urls_custom", "vrt-be.tsv")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
LANGS = ("nl", "en", "fr", "de")
PATH_DATE = re.compile(r"/vrtnws/[a-z]{2}/(\d{4})/(\d{2})/(\d{2})/")
JSON_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')

TARGET_PER_DAY = 25      # verified URLs wanted per day
CAP_PER_DAY = 34         # page fetches spent per day at most
TIME_BUDGET = 950        # seconds for the verification phase (script must stay < 20 min)
MIN_TEXT = 2500          # characters of visible text required on the page


def weeks_touching(start, end):
    """(isoyear, isoweek) pairs covering [start-8d, end+8d]."""
    d = start - timedelta(days=8)
    stop = end + timedelta(days=8)
    out = []
    while d <= stop:
        y, w, _ = d.isocalendar()
        if (y, w) not in out:
            out.append((y, w))
        d += timedelta(days=1)
    return out


def visible_text(html):
    s = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", html)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s)


def page_date(html):
    m = JSON_DATE.search(html)
    if not m:
        return None
    raw = m.group(1)
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def collect_candidates(t0):
    """{iso day: [url, ...]} from the weekly per-language sitemaps."""
    per_day = {}
    seen = set()
    for lang in LANGS:
        for (y, w) in weeks_touching(START, END):
            if time.monotonic() - t0 > 240:
                print("WARN sitemap phase over budget, stopping early", flush=True)
                return per_day
            url = "https://www.vrt.be/vrtnws/%s.sitemap.article.%d.%02d.xml" % (lang, y, w)
            try:
                status, text, _ = fetch(url)
            except Exception as exc:
                print("WARN sitemap %s err %s" % (url, exc.__class__.__name__), flush=True)
                continue
            if status != 200 or not text:
                continue
            try:
                root = ET.fromstring(text)
            except ET.ParseError:
                print("WARN sitemap parse error %s" % url, flush=True)
                continue
            for node in root.findall("s:url", NS):
                loc = node.find("s:loc", NS)
                if loc is None or not loc.text:
                    continue
                u = loc.text.strip()
                m = PATH_DATE.search(u)
                if not m:
                    continue
                try:
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    continue
                if not (START <= d <= END) or u in seen:
                    continue
                seen.add(u)
                per_day.setdefault(d.isoformat(), []).append(u)
    return per_day


def main():
    t0 = time.monotonic()
    days = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
    cand = collect_candidates(t0)
    total_cand = sum(len(v) for v in cand.values())
    print("sitemap phase: %d candidate URLs over %d days in %ds"
          % (total_cand, len(cand), int(time.monotonic() - t0)), flush=True)

    kept = {d: [] for d in days}
    used = {d: set() for d in days}
    stat = {"ok": 0, "http": 0, "nodate": 0, "dateoff": 0, "thin": 0, "budget": 0}

    round_i = 0
    while round_i < CAP_PER_DAY:
        progressed = False
        for d in days:
            bucket = cand.get(d, [])
            need = TARGET_PER_DAY - len(kept[d])
            if need <= 0 or round_i >= len(bucket) or round_i >= CAP_PER_DAY:
                continue
            if time.monotonic() - t0 > TIME_BUDGET:
                stat["budget"] += 1
                round_i = CAP_PER_DAY
                break
            u = bucket[round_i]
            progressed = True
            try:
                status, html, _ = fetch(u)
            except Exception:
                status, html = 0, None
            if status != 200 or not html:
                stat["http"] += 1
                continue
            pd = page_date(html)
            if pd is None:
                stat["nodate"] += 1
                continue
            if abs((pd - date.fromisoformat(d)).days) > 1:
                stat["dateoff"] += 1
                continue
            if len(visible_text(html)) < MIN_TEXT:
                stat["thin"] += 1
                continue
            if u in used[d]:
                continue
            used[d].add(u)
            kept[d].append((u, pd.isoformat()))
            stat["ok"] += 1
        if not progressed:
            break
        round_i += 1

    rows = []
    for d in days:
        rows.extend(sorted(kept[d]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for u, d in rows:
            fh.write("%s\t%s\n" % (u, d))
    os.replace(tmp, OUT)

    print("wrote %d unique URLs to %s in %ds" % (len(rows), OUT, int(time.monotonic() - t0)))
    for d in days:
        print("  %s\t%d" % (d, len(kept[d])))
    print("skips: %s" % json.dumps(stat))


if __name__ == "__main__":
    main()
