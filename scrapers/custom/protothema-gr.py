#!/usr/bin/env python3
"""protothema.gr (Proto Thema, Greece) article URL collector for 2026-09-25..2026-10-25.

Route: robots.txt advertises https://www.protothema.gr/sitemap/Articles/sitemap_index.xml.
That index lists numbered chunks /sitemap/Articles/<N>.xml, ~1000 article ids per chunk,
each <url> carrying <loc> and <lastmod> (UTC).  Chunks are ordered by article id, hence by
publication order, so we walk them from the highest number downwards and stop once a chunk
is entirely older than the window.

Date written = the calendar date of the sitemap <lastmod>, as the site states it.
"""
import sys, os, re, datetime, xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/protothema-gr.tsv")

INDEX = "https://www.protothema.gr/sitemap/Articles/sitemap_index.xml"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
MAX_CHUNKS = 45          # safety cap on requests
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def get(url, tries=3):
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as e:                      # network hiccup
            print(f"  ! {url} exception {e}", file=sys.stderr)
            status, text = 0, None
        if status == 200 and text:
            return text
        print(f"  ! {url} status {status} (try {i + 1})", file=sys.stderr)
        if status in (403, 429, 503):
            import time
            time.sleep(5 * (i + 1))
    return None


def parse_chunk(text):
    """-> list of (url, date) with date = lastmod calendar date."""
    out = []
    text = text.lstrip("\ufeff")
    try:
        root = ET.fromstring(text)
        for u in root.findall("s:url", NS):
            loc = u.find("s:loc", NS)
            lm = u.find("s:lastmod", NS)
            if loc is None or lm is None or not loc.text or not lm.text:
                continue
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lm.text.strip())
            if not m:
                continue
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            out.append((loc.text.strip(), d))
    except ET.ParseError:
        for loc, lm in re.findall(
                r"<loc>(.*?)</loc>\s*<lastmod>(\d{4}-\d{2}-\d{2})", text, re.S):
            out.append((loc.strip(), datetime.date.fromisoformat(lm)))
    return out


def chunk_numbers(text):
    nums = [int(n) for n in re.findall(r"/sitemap/Articles/(\d+)\.xml", text)]
    return sorted(set(nums), reverse=True)


def main():
    rows, seen = [], set()

    idx = get(INDEX)
    chunks = chunk_numbers(idx) if idx else []
    if not chunks:                       # fallback: guess high ids
        chunks = list(range(1920, 1845, -1))
    print(f"index lists {len(chunks)} chunks, newest {chunks[0]}", flush=True)

    stale = 0
    for n in chunks[:MAX_CHUNKS]:
        url = f"https://www.protothema.gr/sitemap/Articles/{n}.xml"
        text = get(url)
        if text is None:
            stale += 1
            if stale >= 3:
                break
            continue
        items = parse_chunk(text)
        if not items:
            stale += 1
            continue
        kept = 0
        for u, d in items:
            if START <= d <= END and u not in seen:
                seen.add(u)
                rows.append((u, d))
                kept += 1
        oldest, newest = min(d for _, d in items), max(d for _, d in items)
        print(f"  chunk {n}: {len(items)} urls, {oldest}..{newest}, kept {kept}", flush=True)
        if newest < START:
            stale += 1
            if stale >= 2:
                print("  reached chunks older than window, stop", flush=True)
                break
        else:
            stale = 0

    rows.sort(key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d.isoformat()}\n")
    os.replace(tmp, OUT)

    counts = Counter(d.isoformat() for _, d in rows)
    print(f"\nwrote {len(rows)} unique urls -> {OUT}")
    for day in sorted(counts):
        print(f"  {day}: {counts[day]}")
    for probe in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"  CHECK {probe}: {counts.get(probe, 0)}")


if __name__ == "__main__":
    main()
