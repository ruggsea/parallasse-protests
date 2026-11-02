#!/usr/bin/env python3
"""Record / R7 (r7.com, Brazil) article lister for 2026-09-25 .. 2026-10-25.

Route: r7.com runs on Arc XP.  robots.txt advertises three sitemap indexes, and
`/arc/outboundfeeds/sitemap-index-byday/` is an index with one sitemap per
publication day (`/arc/outboundfeeds/sitemap{,2,3,...}/YYYY-MM-DD/`).

WHY NOT www.r7.com: the by-day sitemaps on www.r7.com list only
/tudo-do-r7/*, /todos-os-videos/* and /validacao/* paths, and www.r7.com's
robots.txt carries `User-agent: *  Disallow: /tudo-do-r7/*` (checked 2026-10-25,
stable over repeated fetches, md5 a6989cdb...).  polite_fetch therefore refuses
every one of those article URLs, so that route is closed.

The same Arc feeds are served by the section hosts (noticias., esportes.,
entretenimento., record.r7.com), whose article URLs live under per-section paths
(/brasil/, /eleicoes/2026/, /famosos-e-tv/, ...) that their own robots.txt allows
for `User-agent: *` (only /tudo-de-noticias/*, /busca/*, /media/*, /prisma/
todos-os-blogs/* etc. are disallowed, and every candidate is re-checked against
the host's live robots rules before it is written).

Date: r7 appends the local publication day to every article slug as ddmmyyyy
(`...-tse-reune-meta-...-20102026/`), and each day sitemap's <lastmod> equals the
page's article:published_time.  We take the ddmmyyyy from the slug as the listed
date (it is the site's own statement of the publication day, in America/Sao_Paulo)
and fall back to the day encoded in the sitemap path only when a slug has no date
suffix.  Entries whose slug date is outside the window are dropped (evergreen
pages are re-listed in later day sitemaps with their original slug date).

Excluded: /video/ pages and photo galleries (not articles, little text).

Every request goes through polite_fetch (robots.txt first, per-host rate limit,
logged).  Runtime: ~4 index fetches + ~124 day sitemaps, about 2 minutes.
"""
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch, robots_for, UA  # noqa: E402

OUT = ROOT / "data/urls_custom/r7-com.tsv"

START = date(2026, 9, 25)
END = date(2026, 10, 25)

# www.r7.com is deliberately absent: its article paths are robots-disallowed.
HOSTS = [
    "https://noticias.r7.com",
    "https://esportes.r7.com",
    "https://entretenimento.r7.com",
    "https://record.r7.com",
]

# not articles: video stubs, galleries, live pages
SKIP_SEGMENTS = ("/video/", "/videos/", "/fotos/", "/galeria/", "/ao-vivo/", "/tempo-real/")

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
SLUG_DATE_RE = re.compile(r"-(\d{2})(\d{2})(\d{4})(?:-\d+)?/?$")
DAY_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})/?$")


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def slug_date(url):
    """The ddmmyyyy day r7 appends to article slugs, as a date (or None)."""
    m = SLUG_DATE_RE.search(url)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def index_map(host):
    """'YYYY-MM-DD' -> day sitemap URL, per the host's by-day sitemap index."""
    mapping = {}
    status, text, _ = fetch(host + "/arc/outboundfeeds/sitemap-index-byday/")
    if status != 200 or not text:
        print(f"# index {host}: HTTP {status}", flush=True)
        return mapping
    for loc in LOC_RE.findall(text):
        m = DAY_RE.search(loc)
        if m:
            mapping.setdefault(m.group(1), loc)
    return mapping


def robots_allows(url):
    """Exactly the rule polite_fetch applies, so written URLs are fetchable."""
    m = re.match(r"(https?)://([^/]+)", url)
    if not m:
        return False
    scheme, host = m.group(1), m.group(2)
    rp, path = robots_for(host, scheme)
    if path == "backoff":
        return False
    if rp is not None and not rp.can_fetch(UA, url):
        return False
    return True


def main():
    rows = {}          # url -> date
    per_day = {}
    for host in HOSTS:
        days = index_map(host)
        if not days:
            continue
        got = 0
        for d in daterange(START, END):
            key = d.isoformat()
            sm = days.get(key)
            if not sm:
                continue
            status, text, _ = fetch(sm)
            if status != 200 or not text:
                print(f"# {host} {key}: sitemap HTTP {status}", flush=True)
                continue
            for loc in LOC_RE.findall(text):
                if "r7.com" not in loc:
                    continue
                path = loc.split("r7.com", 1)[1]
                if any(seg in path for seg in SKIP_SEGMENTS):
                    continue
                sd = slug_date(loc)
                if sd is not None:
                    if not (START <= sd <= END):
                        continue      # evergreen page re-listed in a later sitemap
                    pub = sd
                else:
                    pub = d          # no date in the slug: trust the sitemap day
                if not (START <= pub <= END):
                    continue
                if loc in rows:
                    continue
                if not robots_allows(loc):
                    continue
                rows[loc] = pub
                per_day[pub] = per_day.get(pub, 0) + 1
                got += 1
        print(f"# {host}: {got} article URLs", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{u}\t{d.isoformat()}\n" for u, d in sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))]
    OUT.write_text("".join(lines))

    print(f"wrote {len(lines)} unique URLs to {OUT}")
    for d in daterange(START, END):
        print(f"{d.isoformat()}\t{per_day.get(d, 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
