#!/usr/bin/env python3
"""Times of India (timesofindia.indiatimes.com) URL scraper, 2026-09-25..2026-10-25.

Route: robots.txt-advertised sitemap index
https://timesofindia.indiatimes.com/staticsitemap/toi/news/sitemap-index.xml
lists one sitemap per calendar day going back to 2000. Each file is a rolling
window of the latest ~10,000 news articles (cap 10000), generated at various
dates, so no single file covers the whole window: the union of the files
named from 2026-08-16 to 2026-10-25 covers 2026-09-24..2026-10-25 (verified
2026-10-25: 2026-September-1.xml carried lastmod 09-24..09-30, the October
daily files carried lastmod back to 10-18; 5 September + 4 October files,
overlapping enough that every day in the window has 600+ URLs).

Date per URL: <lastmod> from the sitemap (IST offset +05:30). Verified against
re-fetched article pages: the JSON-LD datePublished on the page equals the
sitemap lastmod to the minute (e.g. 134600899: sitemap 2026-09-30T23:59:42+05:30,
page datePublished 2026-09-30T23:59:00+05:30; two 10-05 articles identical).
If the same URL appears in several sitemaps with different lastmod, keep the
earliest (closest to publication; lastmod only moves forward).

Fallback: for any day of the window left with <15 URLs, Wayback CDX
(collapse=urlkey, first 200 captures, .cms articles only) supplies URLs dated
by their first capture timestamp. Expected to never fire.
"""
import datetime
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
# The index holds rolling "latest 10000" snapshots named by calendar day; the
# files whose snapshots cover the window are named a few weeks BEFORE the
# window (e.g. 2026-September-1.xml carried 09-24..09-30 on 2026-10-25). Select
# by name date well before START so any regeneration still leaves the window
# covered (union + CDX fallback as last resort).
NAME_FROM = START - datetime.timedelta(days=40)
ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data", "urls_custom", "timesofindia-indiatimes-com.tsv")
INDEX = "https://timesofindia.indiatimes.com/staticsitemap/toi/news/sitemap-index.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.strip().replace("Z", "+00:00")).date()
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s.strip())
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def name_date(url):
    """Date encoded in a sitemap filename like 2026-September-30.xml."""
    fname = url.rsplit("/", 1)[-1]
    m = re.match(r"(\d{4})-([A-Za-z]+)-(\d{1,2})\.xml", fname)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)),
                             datetime.datetime.strptime(m.group(2), "%B").month,
                             int(m.group(3)))
    except ValueError:
        return None


def collect():
    url2date = {}
    st, txt, _ = fetch(INDEX)
    if st != 200 or not txt:
        print(f"sitemap index fetch failed: status {st}", file=sys.stderr)
        return url2date, 0
    root = ET.fromstring(txt)
    wanted = []
    for el in root.findall("sm:sitemap", NS):
        loc_el = el.find("sm:loc", NS)
        if loc_el is None or not loc_el.text:
            continue
        d = name_date(loc_el.text.strip())
        if d is not None and NAME_FROM <= d <= END:
            wanted.append((d, loc_el.text.strip()))
    wanted.sort()
    print(f"index: {len(wanted)} sitemaps named within {NAME_FROM}..{END}", file=sys.stderr)
    failures = 0
    for d, sm_url in wanted:
        st, txt, _ = fetch(sm_url)
        if st != 200 or not txt:
            failures += 1
            print(f"  sitemap {d} status {st} (skipped)", file=sys.stderr)
            continue
        try:
            root = ET.fromstring(txt)
        except ET.ParseError as e:
            failures += 1
            print(f"  sitemap {d} parse error {e} (skipped)", file=sys.stderr)
            continue
        n = 0
        for u in root.findall("sm:url", NS):
            loc_el = u.find("sm:loc", NS)
            lm_el = u.find("sm:lastmod", NS)
            if loc_el is None or not loc_el.text:
                continue
            url = loc_el.text.strip()
            dpub = parse_date(lm_el.text if lm_el is not None else None) or d
            if not (START <= dpub <= END):
                continue
            prev = url2date.get(url)
            if prev is None or dpub < prev:
                url2date[url] = dpub
            n += 1
        print(f"  sitemap {d}: {n} URLs in window", file=sys.stderr)
    return url2date, failures


def cdx_fallback(url2date, days):
    """For days with <15 URLs, take the first captures of the day from Wayback CDX."""
    for d in days:
        url = ("http://web.archive.org/cdx/search/cdx?"
               + "&".join(quote_plus(x) for x in [
                   "url=timesofindia.indiatimes.com/*",
                   f"from={d:%Y%m%d}", f"to={d:%Y%m%d}",
                   "output=json", "collapse=urlkey",
                   "filter=statuscode:200",
                   "limit=300"]))
        st, txt, _ = fetch(url)
        if st != 200 or not txt:
            print(f"  CDX {d} status {st} (skipped)", file=sys.stderr)
            continue
        try:
            import json
            rows = json.loads(txt)
        except Exception:
            try:
                rows = eval(txt)  # JSON list; eval tolerates stray trailing comma
            except Exception:
                print(f"  CDX {d} unparseable (skipped)", file=sys.stderr)
                continue
        added = 0
        for row in rows[1:]:
            orig = row[2]
            if not re.search(r"/articleshow/\d+\.cms", orig):
                continue
            if orig in url2date:
                continue
            url2date[orig] = d
            added += 1
            if added >= 30:
                break
        print(f"  CDX {d}: added {added}", file=sys.stderr)


def main():
    url2date, failures = collect()
    counts = {}
    for d in url2date.values():
        counts[d] = counts.get(d, 0) + 1
    all_days = [START + datetime.timedelta(i) for i in range((END - START).days + 1)]
    thin = [d for d in all_days if counts.get(d, 0) < 15]
    if thin:
        print(f"days thin on URLs {thin} -> CDX fallback", file=sys.stderr)
        cdx_fallback(url2date, thin)
    # recount after fallback
    counts = {}
    for d in url2date.values():
        counts[d] = counts.get(d, 0) + 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url in sorted(url2date, key=lambda u: (url2date[u], u)):
            f.write(f"{url}\t{url2date[url].isoformat()}\n")
    print(f"wrote {len(url2date)} unique URLs to {OUT}")
    missing = [d for d in all_days if not counts.get(d)]
    for d in all_days:
        print(f"{d}: {counts.get(d, 0)} URLs")
    if missing:
        print(f"WARNING no URLs for: {missing}")


if __name__ == "__main__":
    main()
