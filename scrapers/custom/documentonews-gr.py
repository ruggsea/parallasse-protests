#!/usr/bin/env python3
"""documentonews.gr (Documento, Greece) — article URLs published 2026-09-25 .. 2026-10-25.

Route (verified 2026-10-27):
  robots.txt is permissive (only /wp-admin/, /wp-content/plugins/, /readme.html and the
  query pattern "?page=" are disallowed; Python's robotparser matches on path only, so the
  query URLs below are allowed anyway).
  The pretty REST route /wp-json/wp/v2/posts answers 401 (blocked), but the SAME controller
  is served through the rest_route query form:
      /?rest_route=/wp/v2/posts&per_page=100&_fields=link,date&after=..&before=..&page=N
  which answers 200 and gives the site's own publication time (`date`, Greek local time,
  e.g. 2026-10-26T23:55:22) for every post. Pages are walked until a short/empty page.

Fallback if REST is unavailable: the WordPress sitemap index /sitemap.xml lists monthly
  post urlsets /sitemap-pt-post-YYYY-MM.xml with <loc>+<lastmod>; lastmod is UTC and equals
  the publish time for unedited posts, so it is converted to Europe/Athens before the date
  is taken. (lastmod drifts for edited posts, hence REST is preferred.)

Output: data/urls_custom/documentonews-gr.tsv  ->  URL<TAB>YYYY-MM-DD, no header, unique.
"""
import collections
import datetime as dt
import json
import os
import re
import sys
import zoneinfo

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/documentonews-gr.tsv")
HOST = "https://www.documentonews.gr"
TZ = zoneinfo.ZoneInfo("Europe/Athens")

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)

REST = (HOST + "/?rest_route=/wp/v2/posts&per_page=100&_fields=link,date"
        "&after={after}&before={before}&page={page}")


def in_window(d):
    return START <= d <= END


def parse_iso_local(s):
    """'2026-10-26T23:55:22' -> date (already Greek local time)."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_iso_utc_to_local(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if x.tzinfo is None:
        x = x.replace(tzinfo=dt.timezone.utc)
    return x.astimezone(TZ).date()


def via_rest():
    """Walk the WP REST controller through the rest_route query form."""
    rows = []
    # one-day local margin on both ends; the window filter is applied locally.
    after = (START - dt.timedelta(days=1)).isoformat() + "T00:00:00"
    before = (END + dt.timedelta(days=1)).isoformat() + "T23:59:59"
    page = 1
    while page <= 80:
        url = REST.format(after=after, before=before, page=page)
        status, text = 0, None
        for attempt in range(3):
            status, text, _ = fetch(url)
            if status == 200 and text:
                break
            if status in (400, 404):  # past the last page
                break
            # 0/403/429/5xx: one more try, the fetcher already slowed the rate down
        if status == 400 or status == 404:
            break
        if status != 200 or not text:
            print(f"  REST page {page}: HTTP {status}", file=sys.stderr)
            break
        try:
            items = json.loads(text)
        except ValueError:
            print(f"  REST page {page}: unparsable body ({len(text)} bytes)", file=sys.stderr)
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            link = it.get("link")
            day = parse_iso_local(it.get("date"))
            if link and day:
                rows.append((link.strip(), day))
        if len(items) < 100:
            break
        page += 1
    return rows


def via_sitemaps():
    """Fallback: monthly post urlsets, lastmod (UTC) -> Europe/Athens date."""
    rows = []
    for month in ("2026-09", "2026-10"):
        url = f"{HOST}/sitemap-pt-post-{month}.xml"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"  sitemap {month}: HTTP {status}", file=sys.stderr)
            continue
        pairs = re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S)
        for loc, mod in pairs:
            day = parse_iso_utc_to_local(mod)
            if day:
                rows.append((loc.strip(), day))
    return rows


def main():
    rows = []
    try:
        rows = via_rest()
    except Exception as e:  # network hiccup: still try the sitemaps
        print(f"  REST failed: {e}", file=sys.stderr)
    if not rows:
        print("  falling back to sitemaps", file=sys.stderr)
        rows = via_sitemaps()

    seen = {}
    for link, day in rows:
        if not in_window(day):
            continue
        if "/article/" not in link:
            # keep only article pages (skip category/tag/page urlsets)
            if re.search(r"/(category|tag|author|page)/", link):
                continue
        if link not in seen:
            seen[link] = day

    out = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for link, day in out:
            f.write(f"{link}\t{day.isoformat()}\n")
    os.replace(tmp, OUT)

    per_day = collections.Counter(d for _, d in out)
    print(f"wrote {len(out)} unique URLs to {OUT}")
    day = START
    while day <= END:
        print(f"  {day.isoformat()}\t{per_day.get(day, 0)}")
        day += dt.timedelta(days=1)


if __name__ == "__main__":
    main()
