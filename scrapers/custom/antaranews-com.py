import sys
import json
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Polite fetch utility (respect robots.txt, rate limits)
try:
    from polite_fetch import fetch
except Exception:
    import requests
    def fetch(url):
        resp = requests.get(url, timeout=30, headers={"User-Agent": "PoliteFetcher/1.0"})
        resp.raise_for_status()
        return resp.text

from bs4 import BeautifulSoup

START_DATE = datetime(2026, 9, 25).date()
END_DATE = datetime(2026, 10, 25).date()
OUTPUT_TSV = Path("data/urls_custom/antaranews-com.tsv")
OUTPUT_TSV.parent.mkdir(parents=True, exist_ok=True)

def extract_meta_date(soup):
    # Try Open Graph / article meta tag
    meta = soup.find("meta", {"property": "article:published_time"})
    if meta and meta.get("content"):
        try:
            return datetime.fromisoformat(meta["content"].replace('Z', '+00:00')).date()
        except Exception:
            pass
    # Fallback to JSON‑LD
    script = soup.find("script", type="application/ld+json")
    if script:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                date_str = data.get("datePublished")
            elif isinstance(data, list) and data:
                date_str = data[0].get("datePublished")
            else:
                date_str = None
            if date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except Exception:
            pass
    return None

def article_text_length(soup):
    # Main article container may have class "content__article"
    container = soup.find("div", class_="content__article")
    paras = []
    if container:
        paras = [p.get_text(separator=" ", strip=True) for p in container.find_all('p')]
    else:
        paras = [p.get_text(separator=" ", strip=True) for p in soup.find_all('p')]
    return len(" ".join(paras))

def fetch_article(url):
    try:
        html = fetch(url)
    except Exception:
        return None, None
    soup = BeautifulSoup(html, "html.parser")
    pub_date = extract_meta_date(soup)
    txt_len = article_text_length(soup)
    return pub_date, txt_len

def main():
    collected = {}
    page = 1
    while True:
        page_url = f"https://www.antaranews.com/berita?page={page}"
        try:
            html = fetch(page_url)
        except Exception as e:
            print(f"Error fetching pagination page {page}: {e}", file=sys.stderr)
            break
        soup = BeautifulSoup(html, "html.parser")
        article_links = set()
        for a in soup.select('a[href^="https://www.antaranews.com/berita/"]'):
            href = a['href'].split('?')[0]
            article_links.add(href)
        if not article_links:
            print("No article links found – terminating pagination.")
            break
        # Process each discovered link
        for link in sorted(article_links):
            if link in collected:
                continue
            pub_date, txt_len = fetch_article(link)
            if not pub_date:
                continue
            if not (START_DATE <= pub_date <= END_DATE):
                continue
            if txt_len < 1500:
                continue
            collected[link] = pub_date.isoformat()
        # Determine stop condition: earliest date on this page older than start
        dates_on_page = []
        for link in article_links:
            d, _ = fetch_article(link)
            if d:
                dates_on_page.append(d)
        if dates_on_page and min(dates_on_page) < START_DATE:
            print("Encountered articles older than start date – stopping pagination.")
            break
        page += 1
        if page > 200:
            print("Safety page limit hit – stopping.")
            break
    # Write out TSV (URL<TAB>YYYY‑MM‑DD)
    with OUTPUT_TSV.open('w', encoding='utf-8') as out:
        for url, date_str in sorted(collected.items()):
            out.write(f"{url}\t{date_str}\n")
    print(f"Collected {len(collected)} URLs written to {OUTPUT_TSV}")

if __name__ == "__main__":
    main()
