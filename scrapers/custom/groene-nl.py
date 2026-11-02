#!/usr/bin/env python3
"""De Groene Amsterdammer (groene.nl) - articles published 2026-09-25 .. 2026-10-25.

Route: the outlet's own Atom feed, which is complete and paged.
  https://www.groene.nl/feed.atom?page=N   (50 entries per page, newest first,
  <link rel="last"> gives the last page number).  robots.txt allows it (only
  /*?*q=* , /campagnes/, /abonneren/, /agenda/18x are disallowed).
The sitemaps (robots Sitemap: /sitemaps/sitemap.xml.gz -> sitemap1/2.xml.gz,
70k URLs) carry only <lastmod>, which is *edit* time here: 6,437 URLs share the
timestamp 2026-10-19T12:34 and 246 share 2026-10-20T13:13 (bulk re-saves), so
lastmod cannot be used as a publication date.  The feed's <published> matches the
article page's JSON-LD "datePublished" exactly (checked on 2026-09-30, 10-10, 10-20).

Each candidate article page is fetched once to (a) confirm the date against the
page's own datePublished/<time datetime> and (b) keep only pieces whose page
carries a real body of text - short paywalled notices would not survive the
"1500+ characters" check.

Output: data/urls_custom/groene-nl.tsv, one line "URL<TAB>YYYY-MM-DD", no header.
"""
import sys, os, re, html, collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/groene-nl.tsv")
FEED = "https://www.groene.nl/feed.atom"
START, END = "2026-09-25", "2026-10-25"
MAX_FEED_PAGES = 25
MIN_TEXT = 1900          # crude page-text chars; keeps pieces with a real body
MAX_ARTICLE_FETCH = 400


def feed_entries():
    """[(url, published_date, title)] for every feed entry, newest first."""
    rows, pages = [], 0
    for page in range(1, MAX_FEED_PAGES + 1):
        url = FEED if page == 1 else "%s?page=%d" % (FEED, page)
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print("feed page %d -> HTTP %s, stop" % (page, status))
            break
        pages += 1
        entries = re.findall(r"<entry>(.*?)</entry>", text, re.S)
        if not entries:
            break
        oldest = None
        for e in entries:
            pub = re.search(r"<published>([^<]+)</published>", e)
            link = re.search(r'<link rel="alternate" type="text/html" href="([^"]+)"', e)
            if not (pub and link):
                continue
            day = pub.group(1)[:10]
            oldest = day if oldest is None else min(oldest, day)
            title = re.search(r"<title>(.*?)</title>", e, re.S)
            rows.append((link.group(1).strip(), day,
                         html.unescape(title.group(1)).strip() if title else ""))
        print("feed page %d: %d entries, oldest %s" % (page, len(entries), oldest))
        if oldest and oldest < START:
            break
    return rows


def page_signal(text):
    """(page date or None, crude body-text length)."""
    date = None
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', text)
    if m:
        date = m.group(1)
    else:
        m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', text)
        if m:
            date = m.group(1)
    body = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", text)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    body = re.sub(r"\s+", " ", body).strip()
    tmpl = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", p))
                    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", text))
    return date, max(len(body), len(re.sub(r"\s+", " ", tmpl).strip()))


def main():
    entries = feed_entries()
    seen, cand = set(), []
    for url, day, title in entries:
        if not (START <= day <= END):
            continue
        if url in seen:
            continue
        seen.add(url)
        cand.append((url, day, title))
    print("candidates in window: %d" % len(cand))

    rows, dropped_short, dropped_date, failed = [], [], [], 0
    for url, day, title in cand[:MAX_ARTICLE_FETCH]:
        status, text, _ = fetch(url)
        if status != 200 or not text:
            failed += 1
            rows.append((url, day))          # feed date stands, page unreadable
            continue
        pdate, tlen = page_signal(text)
        use = day
        if pdate and pdate != day:
            # the page's own statement wins when it is close, otherwise drop
            if abs(_days(pdate, day)) <= 1:
                use = pdate
            else:
                dropped_date.append((url, day, pdate))
                continue
        if tlen < MIN_TEXT:
            dropped_short.append((url, use, tlen))
            continue
        rows.append((url, use))

    rows = sorted(set(rows), key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for url, day in rows:
            f.write("%s\t%s\n" % (url, day))

    per_day = collections.Counter(d for _, d in rows)
    print("wrote %d urls -> %s" % (len(rows), OUT))
    for day in sorted(per_day):
        print("  %s  %d" % (day, per_day[day]))
    print("dropped: short=%d date-mismatch=%d page-failed=%d"
          % (len(dropped_short), len(dropped_date), failed))
    for u, d, t in dropped_short[:10]:
        print("   short %s %s %d" % (d, u, t))
    for u, d, p in dropped_date[:5]:
        print("   date  feed=%s page=%s %s" % (d, p, u))


def _days(a, b):
    import datetime
    da = datetime.date(*map(int, a.split("-")))
    db = datetime.date(*map(int, b.split("-")))
    return (da - db).days


if __name__ == "__main__":
    main()
