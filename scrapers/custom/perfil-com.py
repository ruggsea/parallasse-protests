#!/usr/bin/env python3
"""Perfil (perfil.com, Argentina) article URLs published 2026-09-25 .. 2026-10-25.

Route: the site's own monthly archive sitemaps
    https://www.perfil.com/sitemap/archive            (index of months)
    https://www.perfil.com/sitemap/archive/2026/09
    https://www.perfil.com/sitemap/archive/2026/10
Each is a <urlset> with one <loc> + <lastmod> per article; <lastmod> is the
publication/last-edit instant in UTC (+00:00) - verified against
/sitemap/lastposts, which carries the same instants in ART (-03:00), e.g.
archive 2026-10-25T13:19:24+00:00 == lastposts 2026-10-25T10:19:24-03:00.
The date written is that instant in Buenos Aires time (UTC-3): on a sample of
articles published 00:00-04:00 UTC this matched the date the article page
itself states 22/30 times, versus 9/30 for the raw UTC date.
/sitemap/lastposts (ART timestamps, last ~2 days) is folded in as a top-up.

Every request goes through scrapers/polite_fetch.py (robots.txt honoured,
per-host rate limit, logged). ~5 requests total.
"""
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = ROOT / "data/urls_custom/perfil-com.tsv"
START, END = "2026-09-25", "2026-10-25"
ART = timezone(timedelta(hours=-3))
INDEX = "https://www.perfil.com/sitemap/archive"
MONTHS = ["https://www.perfil.com/sitemap/archive/2026/09",
          "https://www.perfil.com/sitemap/archive/2026/10"]
ALSO = ["https://www.perfil.com/sitemap/lastposts"]
SKIP_SECTIONS = (
    "/noticias/fotogaleria/",  # photo galleries: no article text
    "/noticias/guia-de-profesionales-pnt/",  # paid advertorial listings, re-dated by the CMS
    "/la-tapa-del-diario-perfil-",  # image of the day's front page, often <1500 chars
)


def norm(url):
    """The sitemap writes some <loc>s as 'https://https://www.perfil.com/...'."""
    url = re.sub(r"^https?://https?://", "https://", url.strip())
    url = url.replace("http://www.perfil.com", "https://www.perfil.com")
    return url


def local_date(stamp):
    """lastmod -> YYYY-MM-DD in Buenos Aires time, or None."""
    try:
        dt = datetime.fromisoformat(stamp.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ART).date().isoformat()


def get(url, tries=3):
    for attempt in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return text
        print(f"  {url} -> {status} (attempt {attempt + 1}/{tries})", file=sys.stderr)
        if status == -1:  # robots refusal: no retry, route is closed
            return None
    return None


def parse(text):
    """'<loc>u</loc><lastmod>d</lastmod>' pairs; lastmod optional."""
    return re.findall(r"<loc>\s*(.*?)\s*</loc>(?:\s*<lastmod>\s*(.*?)\s*</lastmod>)?", text or "", re.S)


def main():
    found = {}  # url -> earliest local date seen

    def add(url, stamp):
        url = norm(url)
        if not url.startswith("https://www.perfil.com/"):
            return
        if any(s in url for s in SKIP_SECTIONS):
            return
        day = local_date(stamp) if stamp else None
        if not day or not (START <= day <= END):
            return
        if url not in found or day < found[url]:
            found[url] = day

    index = get(INDEX)
    if index:
        months = [norm(u) for u, _ in parse(index)]
        print(f"archive sitemap index: {len(months)} monthly sitemaps", file=sys.stderr)
    for sm in MONTHS + ALSO:
        text = get(sm)
        if text is None:
            print(f"  skipped {sm}", file=sys.stderr)
            continue
        n = 0
        for url, stamp in parse(text):
            before = len(found)
            add(url, stamp)
            n += len(found) - before
        print(f"{sm}: +{n} new URLs in window", file=sys.stderr)

    rows = sorted(found.items())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(f"{u}\t{d}\n" for u, d in rows))

    per_day = Counter(d for _, d in rows)
    print(f"wrote {len(rows)} URLs to {OUT.relative_to(ROOT)}")
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")


if __name__ == "__main__":
    main()
