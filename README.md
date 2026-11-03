# Media coverage of the 2026 youth protests

This repository contains the code and data for the [Scomodo](https://www.scomodo.org) Parallasse piece on the media coverage of the 2026 youth protests. The piece investigates how newspapers covered the youth protests of autumn 2026 (25 September to 25 October) and whether Italian outlets were more hostile to protesters than outlets in other countries.

## Report

The report is written in Italian and can be found in the `report/` folder. The main files are `index.html` and `parallasse_protests_report.pdf`. The charts used in the report are located in the `report/charts/` folder, and the CSV files containing the data are in the `report/csv/` folder.

## Results

The results are based on the model's labels of the stance towards protesters as hostile, neutral, or sympathetic. Intervals are 95% bootstrap intervals over outlets.

- Hostile share, all coverage: Italy 49% (n=1,589) vs others 19% (n=11,664), diff +30.2 points [+18.8, +40.7]
- Hostile share, protests in the outlet's own country: Italy 56% (n=1,233) vs others 20% (n=6,084), diff +35.9 points [+22.1, +48.5]
- Sentences on violence: Italy 41% vs 34%
- Sentences on demands: Italy 19% vs 22%

![Share of hostile articles by country](report/charts/c3_paesi.png)

### Charts

The charts used in this project can be found in the `report/charts/` directory. The following charts are included:

- `c3_paesi`: hostile share by country (above)
- `c1_ostili_italia_altri`: hostile share, Italy and the other countries
- `c2_violenza_richieste`: share of sentences about violence and about the demands
- `c4_settimane`: hostile share week by week
- `c5_orientamento`: hostile share by political leaning of the outlet
- `c6_italia_vs_paese_tutta`, `c6_italia_vs_paese_casa`: Italy compared with each country
- `c6_parole_delegittimanti`: delegitimising words found in the articles

## Checks and limits

- Claude (Anthropic) blind read of 299 articles, title + text only. The model calls hostile more than Claude blind read: Italy model 42.0% vs Claude 32.5% (n=200); others model 19.2% vs Claude 11.1% (n=99). The gap Italy-others on Claude labels is +20.5 points [+4.8, +35.6]. The gap holds, but absolute shares are probably too high. No person has labelled a sample yet.
- Cohen's kappa stance is 0.64 for the main model vs Claude (n=299), and 0.66 between two models (n=598).
- The prompt tells the model the country of the outlet. Removing that line or swapping the country, 598 articles: Italy +0.3 and -0.3 points, others +0.0 and +0.3.

Limits:
- Outlets differ per country.
- The Italian sample includes 32 outlets.
- More details are available in `report/limitations_it.md`.

## Data and models

The data and models used in this project are described below:

- Data: 1,439,388 pages, 320 outlets, 49 countries. Keyword filters + model label kept 18,355 articles on youth protests. 13,253 articles have usable text (long enough, not live blog, not duplicate).
- Relevance check by hand: 73 of 80 were correct for the keyword `protest`, 33 of 40 for the keyword `youth`, and 1 relevant article was missed in 200.
- Labels: from title alone and title + text: stance, main frame, share of sentences on violence and demands, who is quoted, delegitimising words.
- Models: Main Qwen3.8-27B (BF16) on every article. gpt-oss-120b checks a sample of 600. vLLM, temperature 0, 65,536-token window, no prompt cut.
- Leaning: Italian outlets classified by Luca Bagnariol. The data is in `data/leaning_italy.tsv` with a source per outlet.
- Copyright: Article texts are not included. `scrapers/` download again. `data/framing_*.jsonl` only includes the URL, outlet, and model answer.

## Contents

- `analysis/`: `relevance_label.py`, `framing_label.py`, `bias_test.py`, `build_report.py` builds the report from labels, `check_plan.py` checks that the code uses the numbers in `PLAN.md`.
- `scrapers/`: `discover.py`, `fetch_articles.py` generic recipe, `custom/` one per other 391 outlets, `polite_fetch.py` robots.txt, rate-limited.
- `grids/`: LLM agent runs that wrote recipes and scrapers.
- `data/`: countries, outlets, leaning, labels; three largest gzipped.
- `report/`: `index.html`, `parallasse_protests_report.pdf`.
- `design/`: fonts, chart style.

## Running it

To run this project, follow these steps:

1. Create a virtual environment and activate it: `uv venv .venv && source .venv/bin/activate`.
2. Install the required packages: `uv pip install -r requirements.txt`.
3. Scrape the data: `bash scrapers/scrape_all.sh` and `bash scrapers/scrape_custom.sh`.
4. Label the data: `python analysis/relevance_label.py PORT MODEL data/relevance_qwen.jsonl` and `python analysis/framing_label.py A data/framing_A.jsonl - 8`.
5. Check the plan: `python analysis/check_plan.py`.
6. Build the report: `python analysis/build_report.py`.

Note that the labelling scripts require an OpenAI-compatible server (we used vLLM) on ports at the top of each script. `framing_label.py` loads tokenizer from the local Hugging Face cache (`HF_HOME`). `build_report.py` works from label files alone.
