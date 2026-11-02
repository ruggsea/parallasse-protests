#!/bin/bash
# scrape_custom.sh : for every accepted custom scraper (grids/custom/out/<id>.json) without data/articles/<id>.done, fetch its articles (the check already copied data/urls_custom/<id>.tsv to data/urls/<id>.tsv). 4 outlets in parallel.
cd "$(dirname "$0")/.." || exit 1; source .venv/bin/activate
ids=$(for f in grids/custom/out/*.json; do id=$(basename $f .json); [ -f data/articles/$id.done ] || [ ! -f data/urls/$id.tsv ] || echo $id; done)
echo "$ids" | xargs -P 4 -I{} bash -c 'python scrapers/fetch_articles.py {} --workers 3 >> logs/fetch_articles.log 2>&1 && touch data/articles/{}.done'
