#!/usr/bin/env python3
"""Generate per‑day URL TSVs for heute.at news articles.
Reads the sitemap at https://www.heute.at/storage/sitemaps/sitemap_news.xml
and writes files data/urls/YYYY-MM-DD.tsv with columns: url\tlisted_date.
Only includes dates between START and END (inclusive).
"""
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pathlib import Path

START = date(2026, 9, 25)
END = date(2026, 10, 25)

ROOT = Path(__file__).resolve().parent.parent
SITEMAP_URL = "https://www.heute.at/storage/sitemaps/sitemap_news.xml"

def fetch_sitemap(url: str) -> str:
    # reuse polite_fetch library for respectful fetching
    sys.path.insert(0, str(Path(__file__).parent))
    from polite_fetch import fetch
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: HTTP {status}")
    return text

def main():
    xml_text = fetch_sitemap(SITEMAP_URL)
    root = ET.fromstring(xml_text)
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    # iterate over <url> entries
    for url_el in root.findall("ns:url", ns):
        loc = url_el.find("ns:loc", ns).text.strip()
        # publication date is in the news namespace
        news_el = url_el.find("news:news", {"news": "http://www.google.com/schemas/sitemap-news/0.9"})
        if news_el is None:
            continue
        pub_el = news_el.find("news:publication_date", {"news": "http://www.google.com/schemas/sitemap-news/0.9"})
        if pub_el is None:
            continue
        # publication_date format like 2026-10-24T21:46:00+02:00
        try:
            dt = datetime.fromisoformat(pub_el.text.rstrip("Z"))
        except Exception:
            continue
        d = dt.date()
        if START <= d <= END:
            out_dir = ROOT / "data" / "urls"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{d.isoformat()}.tsv"
            # append if not already present
            line = f"{loc}\t{d.isoformat()}\n"
            # simple deduplication: check if line already in file
            if out_path.exists():
                with open(out_path, "r", encoding="utf-8") as f:
                    if line in f.read():
                        continue
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(line)

if __name__ == "__main__":
    main()
