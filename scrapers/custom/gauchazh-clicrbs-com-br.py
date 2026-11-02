#!/usr/bin/env python3
"""Zero Hora (gauchazh.clicrbs.com.br) — article URLs for 2026-09-25..2026-10-25.

Route: primary – Wayback Machine CDX API (respecting robots via polite_fetch).
Fallback – pagination of the "Últimas notícias" page (very slow, may miss some dates).

Writes data/urls_custom/gauchazh-clicrbs-com-br.tsv as "URL<TAB>YYYY-MM-DD".
"""
import os, sys, time, re
from datetime import date, datetime, timedelta
from collections import OrderedDict, Counter

# add path for polite_fetch
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/gauchazh-clicrbs-com-br.tsv")
HOST = "https://gauchazh.clicrbs.com.br"
START = date(2026, 9, 25)
END = date(2026, 10, 25)  # inclusive
WINDOW_DAYS = [(START + timedelta(days=i)) for i in range((END - START).days + 1)]

def in_window(d: date) -> bool:
    return START <= d <= END

def cdx_query():
    """Fetch CDX data, retry on 503/5xx.
    Returns list of (url, date) tuples or empty list.
    """
    base = (
        "https://web.archive.org/cdx/search/cdx?url=gauchazh.clicrbs.com.br/*"
        f"&from={START.isoformat().replace('-','')}"
        f"&to={END.isoformat().replace('-','')}"
        "&output=json&collapse=urlkey"
    )
    for attempt in range(12):
        status, text, _ = fetch(base)
        if status == 200 and text:
            try:
                import json as _json
                data = _json.loads(text)
                return data[1:]  # skip header line
            except Exception as e:
                print(f"CDX JSON parse error: {e}", file=sys.stderr)
                return []
        else:
            print(f"CDX attempt {attempt+1}: HTTP {status}", file=sys.stderr)
            time.sleep(30 * (attempt + 1))
    return []

def via_cdx(rows: OrderedDict):
    entries = cdx_query()
    if not entries:
        return False
    added = 0
    for entry in entries:
        # CDX JSON format: [urlkey, timestamp, original, mime, statuscode, digest, length]
        try:
            url = entry[2]
            ts = entry[1]
            dt = datetime.strptime(ts[:8], "%Y%m%d").date()
        except Exception:
            continue
        if not in_window(dt):
            continue
        if url not in rows:
            rows[url] = dt.isoformat()
            added += 1
    print(f"CDX added {added} URLs", file=sys.stderr)
    return added > 0

def via_ultimas(rows: OrderedDict):
    """Fallback: crawl /ultimas-noticias/ pages until no new URLs.
    Very basic HTML parsing using regex to find /noticia/2026/... links.
    """
    pattern = re.compile(r'href="(\/[^\"]+\/noticia/2026\/\d{2}\/\d{2}\/[^\"]+\.html)"')
    page = 1
    added_total = 0
    while True:
        url = f"{HOST}/ultimas-noticias/" if page == 1 else f"{HOST}/ultimas-noticias/?page={page}"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            break
        matches = set(pattern.findall(text))
        if not matches:
            break
        added_this = 0
        for rel in matches:
            full = HOST + rel
            m = re.search(r"/noticia/2026/(\d{2})/(\d{2})/", rel)
            if not m:
                continue
            dt = date(2026, int(m.group(1)), int(m.group(2)))
            if not in_window(dt):
                continue
            if full not in rows:
                rows[full] = dt.isoformat()
                added_this += 1
        added_total += added_this
        print(f"Page {page}: {added_this} new URLs", file=sys.stderr)
        if added_this == 0:
            break
        page += 1
        time.sleep(1)
    return added_total > 0

def main():
    rows = OrderedDict()
    ok = via_cdx(rows)
    counts = Counter(rows.values())
    thin = [d for d in WINDOW_DAYS if counts.get(d.isoformat(), 0) < 15]
    if not ok or thin:
        print("Falling back to ultimas-noticias crawl", file=sys.stderr)
        via_ultimas(rows)
        counts = Counter(rows.values())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for u, d in rows.items():
            f.write(f"{u}\t{d}\n")
    os.replace(tmp, OUT)
    print(f"wrote {len(rows)} unique URLs to {OUT}")
    for d in WINDOW_DAYS:
        print(f"{d.isoformat()}\t{counts.get(d.isoformat(),0)}")
    missing = [d.isoformat() for d in WINDOW_DAYS if counts.get(d.isoformat(),0)==0]
    if missing:
        print("missing days:", missing, file=sys.stderr)

if __name__ == "__main__":
    main()
