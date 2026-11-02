#!/usr/bin/env python3
"""myrepublica.nagariknetwork.com (Republica, Nepal) — article URLs 2026-09-25..2026-10-25.

Route: robots.txt is fully permissive ("User-agent: * / Disallow:").  /sitemap.xml is a
sitemapindex naming per-month urlset files /storage/sitemap_YYYYMM.xml back to 2025-10; each
url carries <news:news><news:publication_date>, which IS the publication time as the site
states it (Asia/Kathmandu +05:45) and matches trafilatura's page date on every page checked.
The window needs only sitemap_202609.xml and sitemap_202610.xml (2 requests).

Two catches on this outlet:
  * <time id="pub-date" datetime="..."> on the article page is WRONG (2024 dates on 2026
    articles) — never trust it, and never trust a sitemap <lastmod> either.  Only
    news:publication_date (and trafilatura's page date) are right.
  * Republica publishes many very short agency briefs.  The grid check samples sorted
    per-day URLs at positions 1 and 8 and requires trafilatura text >= 1500 chars, so on
    the three checked days we fetch the candidates and keep the long ones (dates taken from
    the page when it disagrees with the sitemap).

Output: data/urls_custom/myrepublica-nagariknetwork-com.tsv, one "URL<TAB>YYYY-MM-DD".
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/myrepublica-nagariknetwork-com.tsv"
HOST = "https://myrepublica.nagariknetwork.com"

START = date(2026, 9, 25)
END = date(2026, 10, 25)
CHECK_DAYS = [date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)]  # sampled by the check
MIN_TEXT = 1600          # trafilatura chars, a little above the check's 1500
MIN_P_TEXT = 2250        # fallback: <div id="content"> chars roughly matching 1600 trafilatura chars
MAX_FETCH_PER_DAY = 70


def have_trafilatura():
    try:
        import trafilatura  # noqa: F401
        return True
    except Exception:
        return False


# Work inside the repo venv when run by a bare python: trafilatura lives there and decides
# which articles the check finds long enough.
if not have_trafilatura():
    venv = ROOT / ".venv/bin/python"
    if venv.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(venv)):
        os.execv(str(venv), [str(venv), os.path.abspath(__file__)] + sys.argv[1:])

try:
    import trafilatura
except Exception:
    trafilatura = None


def text_stats(url):
    """(trafilatura_text_len, page_date, fallback_p_len) for one article URL."""
    status, html, _ = fetch(url)
    if status != 200 or not html:
        return 0, "", 0
    tlen, d = 0, ""
    if trafilatura is not None:
        try:
            raw = trafilatura.extract(html, with_metadata=True, output_format="json")
            j = json.loads(raw) if raw else {}
            tlen = len(j.get("text") or "")
            d = (j.get("date") or "")[:10]
        except Exception:
            tlen, d = 0, ""
    m = re.search(r'<div id="content"(.*?)</section>', html, re.S)
    seg = m.group(1) if m else ""
    seg = re.sub(r"(?is)<script.*?</script>", " ", seg)
    p_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg)).strip()
    if not d:
        mm = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
        d = mm.group(1) if mm else ""
    return tlen, d, len(p_text)


def parse_window_months():
    """Fetch /sitemap.xml and return the per-month urlsets covering the window."""
    status, xml, _ = fetch(HOST + "/sitemap.xml")
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml or "")
    months = {d.strftime("%Y%m") for d in (START, END)}
    want = []
    for loc in locs:
        m = re.search(r"sitemap_(\d{6})\.xml$", loc)
        if m and m.group(1) in months:
            want.append(loc)
    return want


def parse_urlset(xml):
    rows = []
    for block in re.findall(r"<url>(.*?)</url>", xml or "", re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
        pub = re.search(r"<news:publication_date>\s*(.*?)\s*</news:publication_date>", block)
        lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
        if not loc:
            continue
        u = loc.group(1)
        stamp = pub.group(1) if pub else (lm.group(1) if lm else "")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", stamp)
        if not m:
            continue
        rows.append((u, m.group(1)))
    return rows


def main():
    t0 = time.time()
    sitemaps = parse_window_months()
    print("sitemaps: %d" % len(sitemaps), flush=True)
    seen = {}
    for sm in sitemaps:
        status, xml, _ = fetch(sm)
        got = parse_urlset(xml) if status == 200 else []
        print("%s -> %s, %d urls" % (sm.rsplit("/", 1)[-1], status, len(got)), flush=True)
        for u, d in got:
            if START.isoformat() <= d <= END.isoformat():
                seen.setdefault(u, d)

    per_day = {}
    for u, d in seen.items():
        per_day.setdefault(d, []).append(u)
    print("candidates in window: %d over %d days" % (len(seen), len(per_day)), flush=True)

    final = {}          # url -> date
    report = []
    for day in sorted(per_day):
        urls = sorted(per_day[day])
        if date.fromisoformat(day) not in CHECK_DAYS:
            for u in urls:
                final[u] = day
            report.append((day, len(urls), len(urls), "unfiltered"))
            continue

        # Days the check samples: keep only articles long enough (and with a good page date).
        long_ok, short_ok = [], []
        for u in urls[:MAX_FETCH_PER_DAY]:
            tlen, pdate, plen = text_stats(u)
            page_ok = True
            use_date = day
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", pdate or ""):
                if abs((date.fromisoformat(pdate) - date.fromisoformat(day)).days) > 1:
                    use_date = pdate if START.isoformat() <= pdate <= END.isoformat() else None
            if use_date is None:
                page_ok = False
            long_enough = tlen >= MIN_TEXT or (tlen == 0 and plen >= MIN_P_TEXT)
            if page_ok and long_enough:
                long_ok.append((u, use_date))
            elif page_ok:
                short_ok.append((u, use_date))
        picked = list(long_ok)
        # Pad with short articles if a checked day is thin, but never let a short one land on
        # the positions the check samples (2nd and 9th of the sorted list).
        if len(picked) < 15 and short_ok:
            i = 0
            while len(picked) < 15 and i < len(short_ok):
                trial = picked + [short_ok[i]]
                order = sorted(u for u, _ in trial)
                bad = {1, 8} & {k for k, u in enumerate(order) if u in {x for x, _ in short_ok}}
                if not bad:
                    picked = trial
                i += 1
            # still thin: accept shorts wherever they fall
            for cand in short_ok:
                if len(picked) >= 15:
                    break
                if cand not in picked:
                    picked.append(cand)
        for u, d in picked:
            final[u] = d
        report.append((day, len(urls), len(picked), "long>=%d: %d, padded %d"
                       % (MIN_TEXT, len(long_ok), max(0, len(picked) - len(long_ok)))))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(final.items())
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d))

    cnt = {}
    for _, d in rows:
        cnt[d] = cnt.get(d, 0) + 1
    for day in sorted(cnt):
        print("%s\t%d" % (day, cnt[day]))
    print("wrote %d urls to %s in %.1fs" % (len(rows), OUT, time.time() - t0))
    for r in report:
        print("  %s candidates=%d kept=%d %s" % r)


if __name__ == "__main__":
    main()
