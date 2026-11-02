#!/usr/bin/env python3
"""thestar.com (Postmedia, TNCms) — articles published 2026-09-25..2026-10-25.

Route (all via polite_fetch):
  robots.txt: User-agent: * disallows only admin/internal paths; our UA is
  allowed on /tncms/sitemap/* and article pages. It declares
  Sitemap: https://www.thestar.com/tncms/sitemap/editorial.xml
  /tncms/sitemap/editorial.xml is a sitemapindex of PER-DAY files:
      /tncms/sitemap/editorial.xml?date=YYYY-MM-DD   (one per day of 2026)
  each a urlset of <loc> + <lastmod>. The day in the ?date= parameter is the
  site's own statement of the publication day (the file is the outlet's
  editorial sitemap for that date); <lastmod> is the record's last-modified
  time and can drift later, so the listed date is the day D of the file,
  not lastmod.
  Notes: /tncms/sitemap/editorial.xml?year=2026 returns 429 (WAF on that
  variant) — the per-day files are served fine (200). /tncms/sitemap/news.xml
  (Google News) holds only ~48h, too shallow for the window.
Verified: page JSON-LD datePublished date == the day D for sample articles.
"""
import sys, re, collections, datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

OUT = "data/urls_custom/thestar-com.tsv"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
DAY_TMPL = "https://www.thestar.com/tncms/sitemap/editorial.xml?date={d}"

def get(url, tries=4):
    """polite_fetch with retries on transient failures. (status, text)."""
    status, text = 0, None
    for _ in range(tries):
        try:
            status, text, _path = fetch(url)
        except Exception:
            status, text = 0, None
        if status == 200 and text:
            return status, text
        if status == -1:          # robots disallow: route closed
            return status, None
        if status in (429, 500, 502, 503, 504, 0):
            continue
        return status, None
    return status, text

def main():
    seen, lines = set(), []
    d = START
    per_day = {}
    while d <= END:
        status, text = get(DAY_TMPL.format(d=d.isoformat()))
        n = 0
        if status == 200 and text:
            for m in re.finditer(r"<loc>\s*([^<]+?)\s*</loc>", text):
                url = m.group(1).strip()
                if not url.startswith("http"):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                lines.append(f"{url}\t{d.isoformat()}")
                n += 1
        per_day[d.isoformat()] = n
        print(d.isoformat(), status, n)
        d += datetime.timedelta(days=1)

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    print(f"wrote {len(lines)} urls to {OUT}")
    for day, n in per_day.items():
        print(day, n)

if __name__ == "__main__":
    main()
