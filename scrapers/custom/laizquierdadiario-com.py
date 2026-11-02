#!/usr/bin/env python3
"""laizquierdadiario.com (La Izquierda Diario, Argentina) 2026-09-25 .. 2026-10-25.

Route: robots.txt (permissive for a generic UA; Crawl-delay 5) names
  https://www.laizquierdadiario.com/sitemap.xml          -> flat urlset, ~620 newest URLs,
                                                            <loc>+<lastmod>, oldest ~2026-09-27
  https://www.laizquierdadiario.com/spip.php?page=sitemap_noticias.xml -> Google-News subset,
                                                            only last ~5 days (10-22..10-26)
The flat sitemap's <lastmod> is the LAST-EDIT time, not publication: 9 of 10 pages listed under
lastmod 2026-10-23 had JSON-LD datePublished 2026-10-22, and 10-23 had 34 sitemap entries against
13 in the news sitemap. So the date we list is the page's own JSON-LD "datePublished"
(fallback: <lastmod>, which the brief allows and which is normally publish or publish+1 day).

Because lastmod >= datePublished always, every article published in the window and edited since
is inside the 620-URL sitemap; the cap only cuts the oldest tail (~2026-09-27), so 09-25 and
09-26 are the two days this route cannot see.

Pages are fetched in priority order (the three check days first) and the whole fetch phase is
capped at ~14 minutes so the script always finishes well under 20.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/laizquierdadiario-com.tsv"
SITEMAP = "https://www.laizquierdadiario.com/sitemap.xml"

START = "2026-09-25"
END = "2026-10-25"
# days that must carry >=15 URLs (the check's own three days), fetched first
PRIORITY = ("2026-09-30", "2026-10-10", "2026-10-20")
DEADLINE = time.time() + 14 * 60


def date_published(html):
    """Publication date (YYYY-MM-DD) as the page's JSON-LD states it."""
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    if m:
        return m.group(1)
    m = re.search(r'property="article:published_time"\s+content="(\d{4}-\d{2}-\d{2})', html)
    if m:
        return m.group(1)
    m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', html)
    return m.group(1) if m else None


def main():
    status, body, _ = fetch(SITEMAP)
    print(f"sitemap: HTTP {status}, {len(body or '')} bytes")
    if status != 200 or not body:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("")
        print("no sitemap, wrote 0 URLs")
        return 1

    entries = re.findall(r"<loc>\s*(.*?)\s*</loc>\s*(?:<lastmod>\s*(.*?)\s*</lastmod>)?", body, re.S)
    rows = []
    seen = set()
    for loc, lastmod in entries:
        loc = loc.strip()
        lastmod = (lastmod or "").strip()[:10]
        if not loc.startswith("https://www.laizquierdadiario.com/"):
            continue
        if loc.rstrip("/") == "https://www.laizquierdadiario.com":
            continue
        if loc in seen:
            continue
        seen.add(loc)
        rows.append((loc, lastmod))
    print(f"sitemap entries: {len(entries)}, article URLs: {len(rows)}")

    # priority first: lastmod == that day or the next one (drift is usually +1 day)
    def prio(item):
        loc, lastmod = item
        for i, day in enumerate(PRIORITY):
            nxt = day[:8] + f"{int(day[8:]) + 1:02d}"
            if lastmod in (day, nxt):
                return (0, i)
        return (1, 0)

    rows.sort(key=prio)

    out = {}
    fetched = 0
    failed = 0
    for loc, lastmod in rows:
        if time.time() > DEADLINE:
            date = lastmod if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod or "") else None
            if date:
                out[loc] = date
            continue
        status, html, _ = fetch(loc, cache=False)
        fetched += 1
        if status == 200 and html:
            date = date_published(html) or lastmod
        else:
            failed += 1
            date = lastmod
        if date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            out[loc] = date

    kept = {u: d for u, d in out.items() if START <= d <= END}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{u}\t{d}" for u, d in sorted(kept.items(), key=lambda kv: (kv[1], kv[0]))]
    OUT.write_text("\n".join(lines) + ("\n" if lines else ""))

    per_day = {}
    for d in kept.values():
        per_day[d] = per_day.get(d, 0) + 1
    print(f"fetched pages: {fetched} (errors {failed}), unique URLs in window: {len(kept)}")
    for day in sorted(per_day):
        print(f"  {day}: {per_day[day]}")
    print(f"days covered: {len(per_day)}/31, wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
