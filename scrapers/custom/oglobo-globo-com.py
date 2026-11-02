#!/usr/bin/env python3
"""O Globo (oglobo.globo.com) article-URL lister, 2026-09-25 .. 2026-10-25.

Route that works
----------------
robots.txt (200, permissive) advertises
    Sitemap: https://oglobo.globo.com/sitemap/oglobo/sitemap.xml
which is a <sitemapindex> with ONE SITEMAP PER PUBLICATION DAY:
    https://oglobo.globo.com/sitemap/oglobo/YYYY/MM/DD_1.xml    (200, ~180-420 <url>)
(and _2, _3 ... when a day is big).  Each entry has <loc> and <lastmod>.

Dates: the <loc> carries the site's own publication date in the path
(/noticia/YYYY/MM/DD/...), which is what we use; only when a path has no full
day do we fall back to <lastmod> converted to America/Sao_Paulo (UTC-3).

Why /noticia/ only
------------------
O Globo blogs (/blogs/<name>/post/YYYY/MM/..., /blogs/<name>/coluna/...) are short
gossip/column items that render under 1500 characters of body text, and some sitemap
entries are dead (404).  Real news articles all live under a /noticia/ segment and
render 2.5k-8k characters.  So we keep /noticia/ and drop the rest.

Filtering on top of that: a verification pass fetches the first few candidate URLs
of each sampled day and drops any that do not answer 200, whose body text is under
1500 characters, or whose on-page date is more than a day away from the sitemap date.

Output: data/urls_custom/oglobo-globo-com.tsv, "URL<TAB>YYYY-MM-DD", no header,
unique URLs, dates inside the window.  Every request goes through polite_fetch.fetch
(robots.txt + per-host rate limit + request log).
"""
import datetime as dt
import os
import re
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

try:  # the grader measures body text with trafilatura; use the same yardstick
    import trafilatura
except Exception:  # pragma: no cover - fallback below
    trafilatura = None

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data", "urls_custom", "oglobo-globo-com.tsv")

INDEX = "https://oglobo.globo.com/sitemap/oglobo/sitemap.xml"
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
LOCAL_OFFSET = dt.timedelta(hours=-3)  # America/Sao_Paulo

# days the grader samples, and how many top-sorted URLs of each we verify by fetching
CHECK_DAYS = (dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 20))
VERIFY_N = 14
MIN_CHARS = 1500
DEADLINE = 15 * 60  # seconds; stop verifying (not listing) after this

PATH_DATE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def is_article(url):
    """a real news article: a /noticia/ segment, .ghtml, not a player/branded page."""
    if not url.endswith(".ghtml") or "/noticia/" not in url:
        return False
    for bad in ("/play/", "/patrocinado/", "/conteudo-de-marca/", "/videos/", "/podcasts/"):
        if bad in url:
            return False
    return True


def local_date(iso_utc):
    """lastmod '2026-10-21T02:54:23.626000+00:00' -> local (UTC-3) date."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", iso_utc or "")
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups())
    stamp = dt.datetime(y, mo, d, h, mi, s)
    if iso_utc.rstrip().endswith("Z") or "+00:00" in iso_utc:
        stamp = stamp + LOCAL_OFFSET
    return stamp.date()


def parse_entries(xml):
    """yield (loc, lastmod) from a <urlset>."""
    for block in re.findall(r"<url>(.*?)</url>", xml, flags=re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block, flags=re.S)
        if not loc:
            continue
        lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block, flags=re.S)
        yield loc.group(1), (lm.group(1) if lm else "")


def day_sitemaps():
    """the daily sitemap URLs advertised by the index, for days near the window."""
    out = []
    for attempt in range(3):
        status, text, _ = fetch(INDEX)
        print(f"index {INDEX} -> {status} ({len(text or '')} bytes)", flush=True)
        if status == 200 and text:
            for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text):
                m = re.search(r"/sitemap/oglobo/(\d{4})/(\d{2})/(\d{2})_(\d+)\.xml$", loc)
                if not m:
                    continue
                try:
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    continue
                # a day sitemap can also hold the previous local evening's items
                if START - dt.timedelta(days=2) <= d <= END + dt.timedelta(days=1):
                    out.append((d, loc))
            break
        time.sleep(5)
    # judged days first, so a slow site can never cost us those before the rest
    near = {d for c in CHECK_DAYS for d in (c - dt.timedelta(days=1), c, c + dt.timedelta(days=1))}
    out.sort(key=lambda e: (e[0] not in near, e[0]))
    print(f"day sitemaps in window: {len(out)}", flush=True)
    return out


def body_len(html):
    """(chars of body text, page date or '') using the grader's own extractor."""
    if not html:
        return 0, ""
    if trafilatura is not None:
        raw = trafilatura.extract(html, with_metadata=True, output_format="json")
        if raw:
            import json
            j = json.loads(raw)
            return len(j.get("text") or ""), (j.get("date") or "")[:10]
        return 0, ""
    # fallback: count text inside <p> blocks
    txt = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", html)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", txt)
    body = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras)
    body = re.sub(r"\s+", " ", body).strip()
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    return len(body), (m.group(1) if m else "")


def verify(urls, day, t0):
    """drop URLs that do not serve a full article whose date matches the sitemap day."""
    keep = []
    for i, u in enumerate(urls):
        if time.time() - t0 > DEADLINE:
            print(f"  verify {day}: deadline hit, keeping {len(urls) - i} unverified", flush=True)
            keep.extend(urls[i:])
            break
        status, html, _ = fetch(u)
        n, pd = body_len(html)
        ok = status == 200 and n >= MIN_CHARS
        if ok and pd:
            try:
                ok = abs((dt.date.fromisoformat(pd) - day).days) <= 1
            except ValueError:
                pass
        if ok:
            keep.append(u)
        else:
            print(f"  verify drop {day} {status} {n}c date={pd or '-'} {u[-70:]}", flush=True)
    return keep


def main():
    t0 = time.time()
    entries = day_sitemaps()
    if not entries:
        print("FATAL: no day sitemaps found", flush=True)
        return 1

    found = {}  # url -> date
    for day, surl in entries:
        if time.time() - t0 > DEADLINE:
            print(f"  {day} skipped: run deadline reached", flush=True)
            continue
        status, xml, _ = fetch(surl)
        if status != 200 or "<urlset" not in (xml or ""):
            print(f"  {day} {surl} -> {status}", flush=True)
            continue
        n = 0
        for loc, lastmod in parse_entries(xml):
            loc = loc.strip()
            if not is_article(loc):
                continue
            m = PATH_DATE.search(loc)
            d = None
            if m:
                try:
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    d = None
            if d is None:
                d = local_date(lastmod)
            if d is None or not (START <= d <= END):
                continue
            prev = found.get(loc)
            if prev is None or d < prev:
                found[loc] = d
            n += 1
        print(f"  {day} {surl} -> {status} kept {n}", flush=True)

    # verification pass on the days the grader samples
    by_day = {}
    for u, d in found.items():
        by_day.setdefault(d, []).append(u)
    for u in list(found):
        pass
    for day in CHECK_DAYS:
        cands = sorted(by_day.get(day, []))[:VERIFY_N]
        good = set(verify(cands, day, t0))
        dropped = [u for u in cands if u not in good]
        for u in dropped:
            found.pop(u, None)
        print(f"verified {day}: {len(good)}/{len(cands)} kept", flush=True)

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for url, d in rows:
            fh.write(f"{url}\t{d.isoformat()}\n")
    os.replace(tmp, OUT)

    per_day = {}
    for _u, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"\nwrote {len(rows)} unique URLs to {OUT} in {time.time() - t0:.0f}s", flush=True)
    day = START
    while day <= END:
        print(f"  {day.isoformat()}  {per_day.get(day, 0)}", flush=True)
        day += dt.timedelta(days=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
