#!/bin/bash
# scrape_all.sh : for every verified recipe without data/articles/<id>.done, discover urls then fetch articles. 6 outlets in parallel. Rerun to pick up new recipes.
cd "$(dirname "$0")/.." || exit 1; source .venv/bin/activate
ids=$(for f in grids/recipes/out/*.json; do id=$(basename $f .json); [ -f data/articles/$id.done ] && continue; python -c "import json,sys;sys.exit(0 if json.load(open('$f'))['list_templates'] else 1)" && echo $id; done)
echo "$ids" | xargs -P 6 -I{} bash -c 'python scrapers/discover.py {} >> logs/discover.log 2>&1 && python scrapers/fetch_articles.py {} --workers 3 >> logs/fetch_articles.log 2>&1 && touch data/articles/{}.done'
