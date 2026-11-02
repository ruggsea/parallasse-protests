#!/usr/bin/env python3
"""geenstijl.nl article lister for 2026-09-25 .. 2026-10-25.

Route (worked out 2026-10-27):
  * robots.txt is 404 on both geenstijl.nl and www.geenstijl.nl -> assumed open.
  * No sitemap exists (/sitemap.xml, /sitemap_index.xml, /news-sitemap.xml, /feed/ all 404).
  * The site is a Next.js app; article URLs are /<numeric id>/<slug>.
  * /archieven/maandelijks/YYYY/MM is a month listing that gives, for each article,
    "DD-MM-YY | HH:MM" plus the /<id>/<slug> link  (site-stated publication time).
  * The month listing is INCOMPLETE: ~25% of live article ids are absent from it.
    So after the two month pages we walk the numeric id range covered by the window
    (archive ids are a good proxy for "which ids belong to which weeks") and fetch the
    ids the listing did not give us. Each such page carries JSON-LD
    "datePublished":"YYYY-MM-DDTHH:MM:SS" (site local, Europe/Amsterdam) and its own
    /<id>/<slug> path, so date and canonical URL both come from the site.
"""
import re
import sys
from pathlib import Path

ROOT = Path(".")
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = ROOT / "data/urls_custom/geenstijl-nl.tsv"
BASE = "https://www.geenstijl.nl"
WIN_START, WIN_END = "2026-09-25", "2026-10-25"
ROW_RE = re.compile(
    r'<p class="mb-0\.5">(\d{2})-(\d{2})-(\d{2}) \| \d{2}:\d{2}</p>.*?href="/(\d{6,8})/([a-z0-9-]+)"',
    re.S,
)
DP_RE = re.compile(r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})')


def fetch_month(year, month):
    """Return {id: (date, slug)} from a monthly archive page."""
    url = f"{BASE}/archieven/maandelijks/{year}/{month:02d}"
    status, text, _ = fetch(url)
    out = {}
    if status != 200 or not text:
        print(f"# archive {url} -> HTTP {status}", file=sys.stderr)
        return out
    for d, mo, y, aid, slug in ROW_RE.findall(text):
        date = f"20{y}-{mo}-{d}"
        out.setdefault(int(aid), (date, slug))
    print(f"# archive {year}-{month:02d} -> HTTP {status}, {len(out)} rows", file=sys.stderr)
    return out


def fetch_article(aid):
    """Return (date, slug) for an article id, or None."""
    status, text, _ = fetch(f"{BASE}/{aid}/x")
    if status != 200 or not text:
        return None
    m = DP_RE.search(text)
    if not m:
        return None
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    s = re.search(r'/%d/([a-z0-9-]+)' % aid, text)
    slug = s.group(1) if s else "x"
    return date, slug


def main():
    known = {}
    for year, month in ((2026, 8), (2026, 9), (2026, 10), (2026, 11)):
        known.update(fetch_month(year, month))

    inwin = {a: v for a, v in known.items() if WIN_START <= v[0] <= WIN_END}
    if inwin:
        lo, hi = min(inwin) - 30, max(inwin) + 30
    else:  # archive unreachable: fall back to a wide fixed id range
        lo, hi = 5192000, 5192760
    print(f"# window ids {lo}..{hi} ({hi - lo + 1} candidates, "
          f"{len(inwin)} already dated by the archives)", file=sys.stderr)

    fetched = 0
    for aid in range(lo, hi + 1):
        if aid in known:
            continue
        got = fetch_article(aid)
        fetched += 1
        if got:
            known[aid] = got
        if fetched % 40 == 0:
            print(f"# {fetched} id probes done", file=sys.stderr)
    print(f"# id probes: {fetched}", file=sys.stderr)

    rows = set()
    for aid, (date, slug) in known.items():
        if WIN_START <= date <= WIN_END:
            rows.add((f"{BASE}/{aid}/{slug}", date))
    urls = sorted(rows, key=lambda r: (r[1], r[0]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for url, date in urls:
            f.write(f"{url}\t{date}\n")

    per_day = {}
    for _, date in urls:
        per_day[date] = per_day.get(date, 0) + 1
    print(f"wrote {len(urls)} unique urls to {OUT}")
    for date in sorted(per_day):
        print(f"{date}\t{per_day[date]}")


if __name__ == "__main__":
    main()
