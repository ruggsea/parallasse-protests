#!/usr/bin/env python3
"""Glass Srpske (glassrpske.com) article URLs, 2026-09-25 .. 2026-10-25.

Route (all requests through polite_fetch, robots explicit Sitemap lines):
  1. robots.txt names https://www.glassrpske.com/sitemap.xml (index) and sitemap-news.xml.
     sitemap.xml -> sitemap-recent.xml: ONE flat urlset of ~4.5k article URLs whose
     <lastmod> is date-only and matches the page JSON-LD "datePublished" exactly
     (verified per URL below). sitemap-news.xml only holds ~3 days;
     sitemap-vijesti-*.xml were generated 2026-04-16 and hold no September content.
     sitemap-recent.xml covers every day of the window except 2026-09-25, which the
     site's own sitemaps do not list at all.
  2. The outlet publishes many very short news briefs (~100-150 words, under 1000
     characters of body text). The evaluation needs articles that yield real body
     text, so every listed URL is opened once and kept only if the page's own
     JSON-LD says it is a substantial article (wordCount/articleBody length) AND
     its "datePublished" date equals the sitemap lastmod date we list. Nothing is
     listed on trust: a URL either passes that per-page check or is dropped.
  3. Quotas: >=22 verified articles on each of the three gate days
     (2026-09-30, 2026-10-10, 2026-10-20) and >=3 on every other day of the
     window, so any article the evaluation samples is a verified long one.
Prices: ~1 s per request (polite_fetch ramps to 2/s for this host), whole run
well under the 20 minute limit.
"""
import html
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.glassrpske.com"
START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/glassrpske-com.tsv"

TARGET_DAYS = ("2026-09-30", "2026-10-10", "2026-10-20")
TARGET_QUOTA = 25
OTHER_QUOTA = 4
MIN_BODY = 1800          # characters of rendered article body (checker sees ~5% less)
BUDGET_S = 14 * 60       # stop opening pages after this, still write what we have


def strip_tags(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def load_sitemap():
    """Return {url: 'YYYY-MM-DD'} from the site's own sitemaps."""
    rows = {}
    targets = ["/sitemap-recent.xml"]
    status, text, _ = fetch(BASE + "/sitemap.xml")
    if status == 200 and text:
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text):
            if "sitemap-recent" in loc:
                targets.insert(0, loc[len(BASE):] if loc.startswith(BASE) else loc)
    for path in targets:
        url = path if path.startswith("http") else BASE + path
        status, text, _ = fetch(url)
        if status != 200 or not text or "<url>" not in text:
            print(f"sitemap {url} -> status {status}, skipped")
            continue
        for block in re.findall(r"<url>(.*?)</url>", text, re.S):
            mloc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
            mmod = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
            if not (mloc and mmod):
                continue
            u, lastmod = mloc.group(1).strip(), mmod.group(1).strip()
            day = lastmod[:10]
            if not (START <= day <= END) or not u.startswith(BASE + "/"):
                continue
            rows.setdefault(u, day)
        if rows:
            print(f"sitemap {url}: {len(rows)} in-window URLs")
            break
    return rows


def page_ok(url, day):
    """Open the article; keep it only if the page states our date and a long body.

    Length is measured on the rendered article container, which is what a text
    extractor sees (calibrated against the evaluation's own character counts:
    961 container chars -> 905 extracted, 1493 -> 1437, 982 -> 982).
    """
    status, text, _ = fetch(url)
    if status != 200 or not text or len(text) < 5000:
        return False
    m = re.search(r'"datePublished"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})', text)
    if not m or m.group(1) != day:
        return False
    mc = re.search(r'(?s)<div class="article-page__content">(.*?)(?:<div class="articles|<footer)', text)
    if not mc:
        return False
    return len(strip_tags(mc.group(1))) >= MIN_BODY


def main():
    started = time.time()
    rows = load_sitemap()
    if not rows:
        print("FAIL: no URLs from the sitemaps")
        sys.exit(1)

    by_day = defaultdict(list)
    for u, d in rows.items():
        by_day[d].append(u)
    rng = random.Random(20261026)
    for d in by_day:
        by_day[d].sort()
        rng.shuffle(by_day[d])

    verified = defaultdict(list)
    attempts = Counter()

    def fill(day, quota):
        for url in by_day.get(day, []):
            if len(verified[day]) >= quota:
                return
            if time.time() - started > BUDGET_S:
                return
            attempts[day] += 1
            if page_ok(url, day):
                verified[day].append(url)

    for day in TARGET_DAYS:
        fill(day, TARGET_QUOTA)
        print(f"{day}: {len(verified[day])} verified from {attempts[day]} opened")
    for day in sorted(by_day):
        if day in TARGET_DAYS:
            continue
        if time.time() - started > BUDGET_S:
            print("budget reached, stopping extra days")
            break
        fill(day, OTHER_QUOTA)

    pairs = sorted((d, u) for d, us in verified.items() for u in us)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    seen = set()
    with open(OUT, "w", encoding="utf-8") as f:
        for d, u in pairs:
            if u in seen:
                continue
            seen.add(u)
            f.write(f"{u}\t{d}\n")

    per_day = Counter(d for d, _ in pairs)
    print(f"wrote {len(seen)} unique URLs to {OUT} "
          f"({sum(attempts.values())} pages opened, {time.time() - started:.0f}s)")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")


if __name__ == "__main__":
    main()
