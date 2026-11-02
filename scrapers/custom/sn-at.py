#!/usr/bin/env python3
"""Salzburger Nachrichten (sn.at) URL lister for 2026-09-25 .. 2026-10-25.

Route
-----
robots.txt (https://www.sn.at/robots.txt, 200, general `User-agent: *` allows everything but
/admin/, /_/, ?_FRAME=, *_FORMAT=PRINT, /register/, /import/, /abfall/) names
https://www.sn.at/portal-artikel.sitemap.xml, which despite its name is a sitemap INDEX:

    <loc>https://www.sn.at/article-2026_10-3.sitemap.xml</loc>

i.e. per-month article sitemaps chunked -1/-2/-3 (about 1400-1600 URLs each, ~10 days per chunk).
The whole 31-day window lives in article-2026_09-{2,3} and article-2026_10-{1,2,3}; each <url>
carries <loc> + <lastmod>.  The other sitemaps named in robots.txt are useless here:
news-artikel.sitemap.xml is a Google News sitemap holding only the last ~48 h (100 entries,
2026-10-25 20:24 .. 2026-10-27 07:26 when checked), and index.sitemap.xml only points at that one.

Dates
-----
<lastmod> on sn.at is close to publish time but is an update time for a minority, so the listed
date is the page's own datePublished as read by trafilatura (the same extractor the checker uses);
<lastmod> is only used to bucket candidates and to reject pages whose own date is more than one
day away from the bucket.

Paywall filter
--------------
sn.at article pages are `<article class="detail paywall ...">` for SN+ pieces: those return 200
but only ~400 characters of teaser text, which is why bare sitemap output fails the 1500-char
sample test.  So every candidate is actually fetched and kept only if trafilatura yields
>= MIN_TEXT chars AND a page date, i.e. the tsv lists nothing that has not been verified.

Budgets: <= MAX_REQ article fetches and a wall-clock deadline, so the run stays well under
20 minutes; the three benchmark days are fetched first and with the widest caps.
"""
import sys, json, re, time, collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # robots + per-host rate limit + request log

ROOT = "."
OUT = ROOT + "/data/urls_custom/sn-at.tsv"
INDEX = "https://www.sn.at/portal-artikel.sitemap.xml"
FALLBACK_SITEMAPS = [
    "https://www.sn.at/article-2026_09-%d.sitemap.xml" % i for i in (1, 2, 3)
] + ["https://www.sn.at/article-2026_10-%d.sitemap.xml" % i for i in (1, 2, 3)]

START, END = "2026-09-25", "2026-10-25"
TARGET_DAYS = {"2026-09-30": 130, "2026-10-10": 100, "2026-10-20": 130}
OTHER_PER_DAY = 26
MAX_REQ = 1100
MIN_TEXT = 1600          # checker wants 1500; keep a margin
DEADLINE = time.time() + 15 * 60

_rows = {}               # url -> date


def write_tsv():
    rows = sorted(((d, u) for u, d in _rows.items()))
    with open(OUT, "w") as f:
        for d, u in rows:
            f.write("%s\t%s\n" % (u, d))
    return rows


def extract(html):
    """Return (text, page_date) using the same extractor as the checker."""
    try:
        import trafilatura
        t = trafilatura.extract(html or "", with_metadata=True, output_format="json")
        if not t:
            return "", ""
        j = json.loads(t)
        return (j.get("text") or ""), (j.get("date") or "")[:10]
    except ImportError:                                     # pragma: no cover
        return "", ""


def sitemaps():
    urls, seen = [], set()
    st, txt, _ = fetch(INDEX)
    print("index %s -> %s, %d bytes" % (INDEX, st, len(txt or "")), flush=True)
    if st == 200 and txt:
        for loc in re.findall(r"<loc>\s*(https://www\.sn\.at/article-\d{4}_\d\d-\d+\.sitemap\.xml)\s*</loc>", txt):
            if loc[:40] + loc[40:48] in ("", ""):
                continue
            if re.search(r"article-2026_(09|10)-\d+\.sitemap\.xml$", loc) and loc not in seen:
                seen.add(loc)
                urls.append(loc)
    if not urls:
        urls = FALLBACK_SITEMAPS
    return sorted(urls)


def candidates():
    """[(url, lastmod_date)] from the per-month article sitemaps."""
    seen, rows = set(), []
    for sm in sitemaps():
        st, txt, _ = fetch(sm)
        n = 0
        if st == 200 and txt:
            for blk in re.findall(r"<url>(.*?)</url>", txt, re.S):
                m = re.search(r"<loc>\s*(\S+?)\s*</loc>", blk)
                d = re.search(r"<lastmod>\s*(\d{4}-\d\d-\d\d)", blk)
                if not m or not d:
                    continue
                u = m.group(1)
                if u in seen:
                    continue
                seen.add(u)
                rows.append((u, d.group(1)))
                n += 1
        print("sitemap %s -> %s, %d urls" % (sm.rsplit("/", 1)[-1], st, n), flush=True)
    return rows


def order(rows):
    """Target days first (own caps), then remaining days round-robin, sections interleaved."""
    by_day = collections.defaultdict(list)
    for u, d in rows:
        if "2026-09-24" <= d <= "2026-10-26":
            by_day[d].append(u)

    def spread(urls):
        # interleave sections so a day never contributes only /briefe-an-die-sn/ etc.
        sec = collections.defaultdict(list)
        for u in sorted(set(urls)):
            m = re.match(r"https://www\.sn\.at/([^/]+)/", u)
            sec[m.group(1) if m else "_"].append(u)
        out, keys, i = [], sorted(sec), 0
        while keys:
            k = keys[i % len(keys)]
            if sec[k]:
                out.append(sec[k].pop(0))
                i += 1
            else:
                keys.remove(k)
                i = i % max(1, len(keys))
        return out

    plan = []
    for day, cap in TARGET_DAYS.items():
        plan += spread(by_day.pop(day, []))[:cap]
    others = {d: spread(u) for d, u in by_day.items()}
    idx = collections.Counter()
    while others:
        for d in sorted(others):
            if idx[d] < OTHER_PER_DAY and idx[d] < len(others[d]):
                plan.append(others[d][idx[d]])
                idx[d] += 1
        others = {d: v for d, v in others.items() if idx[d] < min(OTHER_PER_DAY, len(v))}
    return plan


def main():
    rows = candidates()
    print("candidates total: %d" % len(rows), flush=True)
    plan = order(rows)
    print("planned article fetches: %d (max %d)" % (min(len(plan), MAX_REQ), MAX_REQ), flush=True)

    lastmod = {u: d for u, d in rows}
    req = 0
    for u in plan:
        if req >= MAX_REQ or time.time() > DEADLINE:
            print("stopping at %d article fetches (budget/deadline)" % req, flush=True)
            break
        req += 1
        st, html, _ = fetch(u)
        if st != 200 and st in (0, 500, 502, 503, 504) and req < MAX_REQ:
            time.sleep(2)
            req += 1
            st, html, _ = fetch(u)
        if st != 200 or not html:
            continue
        text, pdate = extract(html)
        if not pdate or len(text) < MIN_TEXT:
            continue
        if not (START <= pdate <= END):
            continue
        lm = lastmod.get(u, "")
        if lm:
            try:
                gap = abs((__import__("datetime").date.fromisoformat(pdate)
                           - __import__("datetime").date.fromisoformat(lm)).days)
            except ValueError:
                gap = 0
            if gap > 1:
                continue
        _rows[u] = pdate
        if req % 100 == 0:
            write_tsv()
            print("  %d fetches, %d kept" % (req, len(_rows)), flush=True)

    rows = write_tsv()
    per = collections.Counter(d for d, _ in rows)
    print("\nwrote %s: %d unique URLs over %d days" % (OUT, len(rows), len(per)))
    for d in sorted(per):
        print("  %s  %d" % (d, per[d]))
    print("article fetches used: %d" % req)


if __name__ == "__main__":
    main()
