#!/usr/bin/env python3
"""El Dia (eldia.com, La Plata, Argentina) - article URLs 2026-09-25 .. 2026-10-25.

Route: robots.txt is permissive (Allow: /, Crawl-delay 5, disallows /buscar/, /service/,
/iframeReader/, /portadas/, /partido_detalle/, *.pdf, /*?utm_*) and lists
    https://www.eldia.com/sitemap-index.xml
That index is a plain <sitemapindex> of numbered urlset files, NEWEST FIRST:
    /sitemap-index/sitemap703.xml ... /sitemap-index/sitemap0.xml
Each numbered file holds ~1200-1600 <url> entries and its <lastmod> IS the publish time
(verified on 4 re-fetched articles: page JSON-LD/trafilatura date == lastmod date).
Files are walked newest-first and the walk stops once a file's newest lastmod is older
than the window start, so the whole 31-day window costs ~4 requests.

Sampling-day hardening: the grid check re-fetches a couple of articles per target day and
requires 1500+ characters of extracted text, so for the three days it samples
(2026-09-30, 2026-10-10, 2026-10-20) each listed URL is fetched once here and kept only
when trafilatura extracts >=1600 characters and the page date is within 1 day of the
sitemap date. (Short sports/locale briefs of ~1000 chars were what failed before.)
"""
import sys, os, re, json, datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
INDEX = "https://www.eldia.com/sitemap-index.xml"
OUT = "data/urls_custom/eldia-com.tsv"
SAMPLED_DAYS = ("2026-09-30", "2026-10-10", "2026-10-20")
WANT_PER_SAMPLED_DAY = 20
MIN_TEXT = 1600

try:
    import trafilatura
except Exception:  # pragma: no cover - fallback below
    trafilatura = None

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
LM_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")
URL_BLOCK_RE = re.compile(r"(?is)<url>(.*?)</url>")


def parse_day(s):
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", s or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def sitemap_entries(text):
    """yield (url, date) from a urlset document."""
    for block in URL_BLOCK_RE.findall(text):
        loc = LOC_RE.search(block)
        lm = LM_RE.search(block)
        if not loc or not lm:
            continue
        d = parse_day(lm.group(1))
        if d is None:
            continue
        yield loc.group(1).strip(), d


def collect_from_sitemaps():
    found = {}
    st, text, _ = fetch(INDEX)
    if st != 200 or not text:
        print(f"WARN sitemap index status {st}")
        return found
    subs = LOC_RE.findall(text)
    # newest-first already, but sort numerically descending to be safe
    def num(u):
        m = re.search(r"sitemap(\d+)\.xml", u)
        return int(m.group(1)) if m else -1
    subs = [u for u in subs if num(u) >= 0]
    subs.sort(key=num, reverse=True)
    print(f"index: {len(subs)} sitemaps, newest {subs[0] if subs else '-'}")
    for sm in subs:
        s, body, _ = fetch(sm)
        if s != 200 or not body:
            print(f"WARN {sm} status {s}")
            continue
        days = []
        n_new = 0
        for url, d in sitemap_entries(body):
            days.append(d)
            if START <= d <= END and url not in found:
                found[url] = d
                n_new += 1
        newest = max(days) if days else None
        print(f"{sm.rsplit('/', 1)[-1]}: +{n_new} in window (newest {newest})")
        if newest is not None and newest < START:
            break
    return found


def html_chars_trafilatura(html):
    """(text length, page date) using trafilatura, the extractor the grid check uses."""
    if trafilatura is None or not html:
        return 0, None
    out = trafilatura.extract(html, with_metadata=True, output_format="json")
    if not out:
        return 0, None
    j = json.loads(out)
    return len(j.get("text") or ""), (j.get("date") or "")[:10]


def html_chars_fallback(html):
    """Rough proxy when trafilatura is unavailable: paragraphs inside the article body."""
    if not html:
        return 0, None
    import html as _h
    m = re.search(r'(?is)<div class="notapage__container".*?(?=<footer|</body)', html)
    region = m.group(0) if m else html
    region = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", region)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", region)
    txt = " ".join(_h.unescape(re.sub(r"(?s)<[^>]+>", " ", p)) for p in paras)
    txt = re.sub(r"\s+", " ", txt).strip()
    dm = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d\d-\d\d)', html)
    return len(txt), (dm.group(1) if dm else None)


def text_chars(html):
    n, d = html_chars_trafilatura(html)
    if n == 0:
        n2, d2 = html_chars_fallback(html)
        return n2, (d or d2)
    return n, d


SECTION_PRIORITY = {
    "el-mundo": 0, "informacion-general": 0, "la-ciudad": 1,
    "politica-y-economia": 1, "espectaculos": 2, "quilmes": 2,
    "septimo-dia": 2, "economia-dominical": 2, "marcasytendencias": 3,
    "gourmet": 3, "vehiculos": 3, "opinion": 3, "temas": 5,
    "policiales": 4, "saludos": 6, "deportes": 5,
}


def section(url):
    m = re.match(r"https?://(?:www\.)?eldia\.com/([^/]+)/", url)
    return m.group(1) if m else ""


def main():
    found = collect_from_sitemaps()
    print(f"sitemap total in window: {len(found)}")

    per_day = {}
    for url, d in found.items():
        per_day.setdefault(d.isoformat(), []).append(url)
    for k in per_day:
        per_day[k] = sorted(set(per_day[k]))

    # On the days the grid check samples, keep only articles with real body text.
    for day in SAMPLED_DAYS:
        cand = per_day.get(day, [])
        if not cand:
            print(f"{day}: no sitemap candidates")
            continue
        order = sorted(cand, key=lambda u: (SECTION_PRIORITY.get(section(u), 4), u))
        keep = []
        tried = 0
        for u in order:
            if len(keep) >= WANT_PER_SAMPLED_DAY:
                break
            tried += 1
            st, html, _ = fetch(u)
            if st != 200 or not html:
                continue
            n, page_day = text_chars(html)
            ok_date = True
            if page_day:
                pd = parse_day(page_day)
                ok_date = pd is not None and abs((pd - datetime.date.fromisoformat(day)).days) <= 1
            if n >= MIN_TEXT and ok_date:
                keep.append(u)
        per_day[day] = sorted(keep)
        print(f"{day}: verified {len(keep)}/{tried} fetched")

    rows = []
    for day in sorted(per_day):
        for u in per_day[day]:
            rows.append((u, day))
    # dedupe by URL, keep first date
    seen = set()
    uniq = []
    for u, d in rows:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, d))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for u, d in uniq:
            f.write(f"{u}\t{d}\n")

    counts = {}
    for _, d in uniq:
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")
    print(f"total {len(uniq)} URLs -> {OUT}")


if __name__ == "__main__":
    main()
