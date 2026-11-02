import json
import re
from datetime import datetime, date
from pathlib import Path

# Ensure project root is on sys.path for module imports
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Polite fetch utility – falls back to urllib if unavailable
try:
    from polite_fetch import fetch
except Exception:
    import urllib.request
    def fetch(url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ClaudeBot/1.0)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")

SITEMAP_URL = "https://tabnak.ir/news-sitemap.xml"
TSV_PATH = Path(__file__).resolve().parents[2] / "data/urls_custom/tabnak-ir.tsv"
JSON_PATH = Path(__file__).resolve().parents[2] / "grids/custom/out/tabnak-ir.json.part"

START_DATE = date(2026, 9, 25)
END_DATE = date(2026, 10, 25)

def parse_sitemap(xml: str):
    """Extract (url, publication_date) pairs from Tabnak news‑sitemap.
    The XML mixes namespaces; a simple regex is sufficient for our needs.
    """
    entries = []
    for block in re.findall(r"<url>(.*?)</url>", xml, flags=re.DOTALL):
        loc_match = re.search(r"<loc>(.*?)</loc>", block)
        date_match = re.search(r"<news:publication_date>(.*?)</news:publication_date>", block)
        if not loc_match or not date_match:
            continue
        url = loc_match.group(1).strip()
        try:
            pub_dt = datetime.fromisoformat(date_match.group(1).strip())
        except ValueError:
            continue
        entries.append((url, pub_dt.date()))
    return entries

def fetch_cdx():
    """Fetch URLs from Wayback CDX API for the target window.
    Returns a tuple: (entries list, success flag, status code).
    """
    cdx_url = (
        "http://web.archive.org/cdx/search/cdx?url=tabnak.ir/*"
        f"&from={START_DATE.isoformat().replace('-', '')}"
        f"&to={END_DATE.isoformat().replace('-', '')}"
        "&output=json&fl=original,timestamp&filter=mimetype:text/html&collapse=urlkey"
    )
    try:
        cdx_resp = fetch(cdx_url)
        cdx_status = getattr(cdx_resp, 'status_code', None)
        cdx_text = cdx_resp.text if hasattr(cdx_resp, 'text') else str(cdx_resp)
        lines = cdx_text.strip().split('\n')
        if not lines:
            return [], False, cdx_status
        entries = []
        for line in lines[1:]:
            parts = line.split(' ')
            if len(parts) != 2:
                continue
            url, ts = parts
            try:
                dt = datetime.strptime(ts[:8], "%Y%m%d").date()
            except Exception:
                continue
            if START_DATE <= dt <= END_DATE:
                entries.append((url, dt))
        return entries, True, cdx_status
    except Exception as e:
        print(f"CDX fetch error: {e}")
        return [], False, None

def main():
    # Fetch the sitemap (respect robots.txt via polite_fetch)
    try:
        sitemap_resp = fetch(SITEMAP_URL)
        sitemap_status = getattr(sitemap_resp, 'status_code', None)
        
        sitemap_xml = sitemap_resp.text if hasattr(sitemap_resp, 'text') else str(sitemap_resp)
        all_entries = parse_sitemap(sitemap_xml)
        sitemap_success = True
    except Exception as e:
        sitemap_status = None
        all_entries = []
        sitemap_success = False
    # Add Wayback CDX fallback entries
    cdx_entries, cdx_success, cdx_status = fetch_cdx()
    # cdx_success already a bool indicating if fetch succeeded
    all_entries.extend(cdx_entries)
    # Filter by the required date window (already filtered in fetch_cdx)
    filtered = [(u, d.isoformat()) for u, d in all_entries if START_DATE <= d <= END_DATE]
    # Deduplicate – keep the latest date if a URL appears multiple times
    uniq = {}
    for u, d in filtered:
        uniq[u] = d
    # Write TSV output
    TSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TSV_PATH.open("w", encoding="utf-8") as f:
        for u, d in sorted(uniq.items()):
            f.write(f"{u}\t{d}\n")
    # Record notes for the manager
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    notes = {
        "script": "scrapers/custom/tabnak-ir.py",
        "sitemap_fetched": sitemap_success,
        "sitemap_status": sitemap_status,
        "cdx_fetched": cdx_success,
        "cdx_status": cdx_status,
        "url_count": len(uniq),
        "date_range": f"{START_DATE.isoformat()} to {END_DATE.isoformat()}",
        "output_tsv": str(TSV_PATH),
    }
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
