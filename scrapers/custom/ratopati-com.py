#!/usr/bin/env python3
"""ratopati.com (Nepali news portal, Laravel CMS) — article URLs 2026-09-25 .. 2026-10-25.

Routes used (all through scrapers/polite_fetch.py, which reads robots.txt first):
  A) URLs  : /category/<slug>?page=N — server-side paginated section listing, ~94 story
             links per page, newest first. (/latest-news ignores ?page=, there are no real
             sitemaps: every unknown path is answered with the SPA home page, and /feed
             RSS is capped at 30 items with no paging.)
  B) dates : /story/<id> carries JSON-LD "datePublished" (the site's own publish time).
             Story ids are an autoincrement counter in publish order (~250 per day), so
             probing one id every ~200 gives date anchors, and every listing id is dated by
             linear interpolation between its two bracketing anchors.

Run: python3 scrapers/custom/ratopati-com.py
Writes data/urls_custom/ratopati-com.tsv (URL<TAB>YYYY-MM-DD) and
       grids/custom/out/ratopati-com.json.part
"""
import sys, re, json, time, html
from datetime import datetime, date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch

START = date(2026, 9, 25)
END = date(2026, 10, 25)
TSV = ROOT / "data/urls_custom/ratopati-com.tsv"
OUT = ROOT / "grids/custom/out/ratopati-com.json.part"
BASE = "https://www.ratopati.com"

PROBE_STRIDE = 200      # ids between date anchors (~0.8 day)
MAX_PROBES = 42
MAX_CATS = 6
MAX_PAGES = 14
PAGES_CAP = 52
VERIFY_N = 5
BUDGET = 150.0          # seconds of network work; TSV is written once this could run out

T0 = time.time()
NREQ = [0]


def get(url):
    NREQ[0] += 1
    st, txt, _ = fetch(url)
    return st, txt


def late():
    return time.time() - T0 > BUDGET


def story_date(txt):
    """JSON-LD datePublished of a story page -> datetime (site local time), or None."""
    m = re.search(r'datePublished"?\s*:\s*"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})', txt)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# ------------------------------------------------------- date anchors from story pages
def probe(id0):
    """First live story id at or just below id0 -> (id, datetime) or None."""
    for k in range(8):
        st, txt = get("%s/story/%d" % (BASE, id0 - k))
        if st == 200 and txt:
            dt = story_date(txt)
            if dt:
                return (id0 - k, dt)
    return None


def build_anchors(top_id):
    anchors = []
    first = probe(top_id)
    if not first:
        return anchors
    anchors.append(first)
    cur = first[0]
    n = 0
    while n < MAX_PROBES and not late():
        n += 1
        nxt = probe(cur - PROBE_STRIDE)
        if not nxt:
            break
        anchors.append(nxt)
        cur = nxt[0]
        if nxt[1].date() < START - timedelta(days=3):
            break
    anchors.sort(key=lambda a: a[0])
    clean = []
    for a in anchors:
        if clean and (a[0] <= clean[-1][0] or a[1] < clean[-1][1]):
            continue
        clean.append(a)
    return clean


def dt_for(anchors, idv):
    """Interpolated publish datetime for a story id, or None if outside the anchored range."""
    if len(anchors) < 2 or idv < anchors[0][0] or idv > anchors[-1][0]:
        return None
    lo, hi = 0, len(anchors) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if anchors[mid][0] <= idv:
            lo = mid
        else:
            hi = mid
    a, b = anchors[lo], anchors[hi]
    if b[0] == a[0]:
        return a[1]
    frac = (idv - a[0]) / float(b[0] - a[0])
    return a[1] + timedelta(seconds=frac * (b[1] - a[1]).total_seconds())


def id_at(anchors, when):
    """Smallest story id whose interpolated publish time is >= `when`."""
    if len(anchors) < 2:
        return None
    a, b = anchors[0], anchors[-1]
    if when <= a[1]:
        return a[0]
    if when >= b[1]:
        return b[0]
    lo, hi = a[0], b[0]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        d = dt_for(anchors, mid)
        if d is not None and d < when:
            lo = mid
        else:
            hi = mid
    return hi


# ------------------------------------------------------------------ listings (URL side)
LINK_RE = re.compile(r'href="((?:https://www\.ratopati\.com)?/story/(\d+)/[^"#?\s]*)"')


def listing(url):
    st, txt = get(url)
    if st != 200 or not txt:
        return []
    seen, out = set(), []
    for href, sid in LINK_RE.findall(txt):
        sid = int(sid)
        if sid in seen:
            continue
        seen.add(sid)
        if not href.startswith("http"):
            href = BASE + href
        out.append((sid, href))
    return out


def homepage():
    """(ranked section slugs, newest story id seen on the front page)."""
    st, txt = get(BASE + "/")
    if st != 200 or not txt:
        return ["headline-news"], 601500
    counts = {}
    for slug in re.findall(r'/category/([a-z0-9\-]+)', txt):
        counts[slug] = counts.get(slug, 0) + 1
    ranked = [s for s, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    ids = [int(x) for x in re.findall(r'/story/(\d+)/', txt)]
    return (ranked[:MAX_CATS] or ["headline-news"]), (max(ids) if ids else 601500)


# ------------------------------------------------------------------------ verification
def page_text_len(txt):
    body = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", txt)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", p)) for p in paras)
    return len(re.sub(r"\s+", " ", text).strip())


def main():
    rows = {}          # story id -> (url, date)
    cats, top_id = homepage()
    anchors = build_anchors(top_id)
    print("anchors: %d  span %s .. %s  (%d ids, requests so far %d)"
          % (len(anchors),
             anchors[0][1].strftime("%Y-%m-%d") if anchors else "-",
             anchors[-1][1].strftime("%Y-%m-%d") if anchors else "-",
             (anchors[-1][0] - anchors[0][0]) if anchors else 0, NREQ[0]))

    if len(anchors) < 2:
        # cannot date anything; leave the stub untouched and say so
        print("FAILED: no date anchors")
        return 1

    id_floor = id_at(anchors, datetime.combine(START - timedelta(days=1), datetime.min.time()))
    print("categories: %s" % ", ".join(cats))

    pages_done = 0
    for slug in cats:
        if pages_done >= PAGES_CAP or late():
            break
        for page in range(1, MAX_PAGES + 1):
            if late() or pages_done >= PAGES_CAP:
                break
            url = "%s/category/%s" % (BASE, slug) if page == 1 else \
                  "%s/category/%s?page=%d" % (BASE, slug, page)
            links = listing(url)
            pages_done += 1
            if not links:
                break
            got = 0
            for sid, href in links:
                d = dt_for(anchors, sid)
                if d is None:
                    continue
                day = d.date()
                if START <= day <= END and sid not in rows:
                    rows[sid] = (href, day)
                    got += 1
            oldest = min(sid for sid, _ in links)
            print("  %s p%-2d links=%-3d new=%-3d oldest_id=%s oldest_id_date=%s"
                  % (slug, page, len(links), got, oldest,
                     (dt_for(anchors, oldest) or datetime(1970, 1, 1)).strftime("%Y-%m-%d")))
            if oldest <= id_floor:
                break

    # ---------- top-up: a floor of URLs on every day (anchors bracket each day exactly)
    MIN_PD, tried, extra = 15, set(), 0
    for k in range((END - START).days + 1):
        day = START + timedelta(days=k)
        if late() or extra >= 14:
            break
        nday = lambda: sum(1 for _, d in rows.values() if d == day)
        if nday() >= MIN_PD:
            continue
        lo = id_at(anchors, datetime.combine(day, datetime.min.time()))
        hi = id_at(anchors, datetime.combine(day + timedelta(days=1), datetime.min.time()))
        if not lo or not hi or hi <= lo + 2:
            continue
        for f in (0.30, 0.45, 0.60, 0.75, 0.88, 0.20, 0.52):
            if nday() >= MIN_PD or late() or extra >= 14:
                break
            sid = lo + int((hi - lo) * f)
            if sid in rows or sid in tried:
                continue
            tried.add(sid)
            extra += 1
            st, txt = get("%s/story/%d" % (BASE, sid))
            dt = story_date(txt) if txt else None
            if st == 200 and dt and dt.date() == day:
                rows[sid] = ("%s/story/%d" % (BASE, sid), day)
        print("  top-up %s -> %d" % (day.isoformat(), nday()))

    # ------------------------------------------------------------------ write the TSV
    items = sorted(rows.items(), key=lambda kv: (-kv[1][1].toordinal(), -kv[0]))
    TSV.parent.mkdir(parents=True, exist_ok=True)
    tmp = TSV.with_suffix(".tsv.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for sid, (href, day) in items:
            fh.write("%s\t%s\n" % (href, day.isoformat()))
    tmp.replace(TSV)

    counts = {}
    for _, (_, day) in items:
        counts[day.isoformat()] = counts.get(day.isoformat(), 0) + 1
    print("wrote %s: %d unique story URLs in %d days (requests %d, %.0fs)"
          % (TSV, len(items), len(counts), NREQ[0], time.time() - T0))
    for day in sorted(counts):
        print("  %s  %d" % (day, counts[day]))

    # --------------------------------------------------------------- sample verification
    probes = []
    for target in ("2026-09-30", "2026-10-10", "2026-10-20"):
        pick = [sid for sid, (_, d) in items if d.isoformat() == target][:2]
        probes.extend((target, sid, href, d) for sid, (href, d) in rows.items() if sid in pick)
    probes = probes[:VERIFY_N]
    ok, checked = 0, []
    for target, sid, href, day in probes:
        st, txt = get(href)
        dt = story_date(txt) if txt else None
        nchars = page_text_len(txt) if txt else 0
        good = bool(st == 200 and dt and abs((dt.date() - day).days) <= 1 and nchars >= 1500)
        ok += good
        line = "  check %s listed=%s page=%s chars=%d %s" % (
            href, day.isoformat(), dt.strftime("%Y-%m-%d") if dt else "none", nchars,
            "OK" if good else "BAD")
        print(line)
        checked.append({"url": href, "listed": day.isoformat(),
                        "page_date": dt.strftime("%Y-%m-%d") if dt else None,
                        "chars": nchars, "ok": good})

    notes = (
        "ratopati.com is a Laravel site with no usable sitemap (every unknown path, including "
        "/sitemap.xml and /wp-sitemap.xml, is answered with the SPA home page), no JSON API "
        "(app.min.js only calls /api/v1/translate), an RSS feed (/feed) capped at 30 items that "
        "ignores ?page=, and a /latest-news list that also ignores ?page=. What does work: "
        "/category/<slug>?page=N paginates server-side (~94 story links per page, newest first), "
        "and every /story/<id> page carries JSON-LD datePublished. Story ids are autoincrement in "
        "publish order (~250 ids per day), so the script probes one /story/<id> every 200 ids to "
        "build date anchors (%d anchors, %s..%s) and dates every listing id by linear interpolation "
        "between its bracketing anchors. /story/<id> without the slug resolves fine, so slugs are "
        "taken from the listings. Result: %d URLs across %d days, %d requests, %.0fs. "
        "%d/%d sampled articles re-fetched with a page date within 1 day and 1500+ chars of text "
        "(min %d chars)."
        % (len(anchors),
           anchors[0][1].strftime("%Y-%m-%d"), anchors[-1][1].strftime("%Y-%m-%d"),
           len(items), len(counts), NREQ[0], time.time() - T0,
           ok, len(checked), min([c["chars"] for c in checked]) if checked else 0)
    )
    payload = {
        "script": "scrapers/custom/ratopati-com.py",
        "notes": notes,
        "requests": NREQ[0],
        "seconds": round(time.time() - T0, 1),
        "pages_listed": pages_done,
        "anchors": [[a[0], a[1].strftime("%Y-%m-%d %H:%M")] for a in anchors],
        "per_day": counts,
        "samples": checked,
    }
    if len(items) < 150:
        payload["low_volume"] = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("notes written to %s" % OUT)
    return 0 if ok == len(checked) else 1


if __name__ == "__main__":
    sys.exit(main())
