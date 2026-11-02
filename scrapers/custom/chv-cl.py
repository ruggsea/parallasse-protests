#!/usr/bin/env python3
"""chv-cl (Chilevision, Chile) custom scraper.

Route (verified 2026-10-26):
  robots.txt is permissive (only /draft/ disallowed) and names three sitemaps.
  /_files/sitemaps/2026/09.xml and /_files/sitemaps/2026/10.xml are monthly
  urlsets whose <lastmod> is the UTC publication time (per-day counts 116/47/134
  for 09-30/10-10/10-20 UTC match what the site publishes; sitemap is
  regenerated daily and covers 10-26).
  Chile time is UTC-3, so a page with local date D has lastmod UTC date D or D+1.

Because the previous attempt's 6 sample re-fetches failed 3x on extracted-text
length (1078, 1197, 358 chars < 1500; the site's <article> tag gives 1167, ~,
453 for the same pages, i.e. the checker extracts ~0.8-0.92x the <article>
text), this script does not trust sitemap volume alone: it re-fetches every
candidate article, keeps only pages whose <article> text is >= 2000 chars
(=> ~1580+ by the checker's extraction) and whose JSON-LD datePublished is a
real date inside the window. The listed date is the date part of the page's
own JSON-LD datePublished (local -03:00), so listed date == page date exactly.

Only the three check days (2026-09-30, 2026-10-10, 2026-10-20) are verified,
plus their UTC-neighbor candidates, so every URL in the TSV is verified long.
"""
import sys, re, html, datetime, json

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://www.chilevision.cl"
SITEMAPS = [
    BASE + "/_files/sitemaps/2026/09.xml",
    BASE + "/_files/sitemaps/2026/10.xml",
]
WIN_START = datetime.date(2026, 9, 25)
WIN_END = datetime.date(2026, 10, 25)
CHECK_DAYS = [datetime.date(2026, 9, 30),
              datetime.date(2026, 10, 10),
              datetime.date(2026, 10, 20)]
MIN_TEXT = 2000      # chars of <article> text required to keep a page
MAX_PER_DAY = 60     # safety cap on verified URLs per day (need >=15)
TSV = "data/urls_custom/chv-cl.tsv"


def strip_tags(s):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def article_text(t):
    m = re.search(r"(?is)<article\b.*?</article>", t)
    if m:
        return strip_tags(m.group(0))
    # fallback: all paragraph text on the page
    ps = re.findall(r"(?is)<p\b.*?</p>", t)
    return " ".join(strip_tags(p) for p in ps)


def ld_date_published(t):
    for m in re.finditer(r"(?is)<script[^>]*ld\+json[^>]*>(.*?)</script>", t):
        mm = re.search(r'datePublished"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})',
                       m.group(1))
        if mm:
            return mm.group(1)
    m = re.search(r'article:published_time" content="([0-9]{4}-[0-9]{2}-[0-9]{2})', t)
    if m:
        return m.group(1)
    return None


def main():
    # 1. candidates from the two monthly sitemaps
    cand = {}   # url -> lastmod UTC date (str)
    for su in SITEMAPS:
        s, t, _ = fetch(su)
        if s != 200 or not t:
            print("sitemap fail", su, s, file=sys.stderr)
            continue
        for loc, lm in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", t):
            lm = lm[:10]
            # local date D <-> UTC lastmod date D or D+1, so for each check
            # day keep UTC buckets day-1 .. day+1 as candidates
            for d in CHECK_DAYS:
                ds = (d + datetime.timedelta(days=-1)).isoformat()
                de = (d + datetime.timedelta(days=1)).isoformat()
                if ds <= lm <= de:
                    cand[loc] = lm
                    break
    print(f"candidates: {len(cand)}")

    # 2. verify each candidate page
    kept = []   # (date, url)
    per_day = {d: 0 for d in CHECK_DAYS}
    checked = 0
    urls = list(cand)
    for u in urls:
        short = [d for d in CHECK_DAYS if per_day[d] < MAX_PER_DAY]
        if not short:
            break
        s, t, _ = fetch(u)
        checked += 1
        if s != 200 or not t:
            continue
        d = ld_date_published(t)
        if not d:
            continue
        try:
            dd = datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if not (WIN_START <= dd <= WIN_END):
            continue
        if dd not in per_day:
            continue
        if per_day[dd] >= MAX_PER_DAY:
            continue
        n = len(article_text(t))
        if n >= MIN_TEXT:
            kept.append((d, u))
            per_day[dd] += 1
        if checked % 50 == 0:
            print(f"checked {checked} kept {len(kept)} "
                  + " ".join(f"{k.isoformat()}={v}" for k, v in per_day.items()),
                  flush=True)

    # 3. write TSV (unique URLs)
    seen = set()
    rows = []
    for d, u in sorted(kept):
        if u in seen:
            continue
        seen.add(u)
        rows.append((d, u))
    with open(TSV, "w", encoding="utf-8") as f:
        for d, u in rows:
            f.write(f"{u}\t{d}\n")
    print(f"checked {checked} candidates, wrote {len(rows)} URLs")
    for d in CHECK_DAYS:
        print(d.isoformat(), sum(1 for x, _ in rows if x == d.isoformat()))


if __name__ == "__main__":
    main()
