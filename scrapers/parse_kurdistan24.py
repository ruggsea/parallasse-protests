import sys, json
from bs4 import BeautifulSoup

def main(html_path):
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    base = 'https://www.kurdistan24.net'
    articles = []
    for article in soup.select('article'):
        # time
        time_tag = article.find_previous('time')
        timestamp = None
        if time_tag:
            # time may be inside span within time
            span = time_tag.find('span', class_='w-fit')
            if span:
                timestamp = span.get_text(strip=True)
        # title and link
        a = article.find('a', href=True)
        if not a:
            continue
        href = a['href']
        if not href.startswith('http'):
            href = base + href
        title_tag = a.find('h3')
        title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)
        articles.append({
            'timestamp': timestamp,
            'title': title,
            'url': href
        })
    # output as JSON lines
    for art in articles:
        print(json.dumps(art, ensure_ascii=False))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python parse_kurdistan24.py <html_file>', file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
