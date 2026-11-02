# parallasse-protests

How did the media cover the youth protests of autumn 2026, and is the Italian coverage more hostile than the coverage in other countries? I did this for Parallasse, the data-journalism column of Scomodo. The suspicion was the question, not the answer: if Italy had come out no worse, the report would say so.

Window: 2026-09-25 to 2026-10-25. The report is in Italian: `report/index.html` and `report/parallasse_protests_report.pdf`, with the charts in `report/charts/` and every number in `report/csv/`.

## Result

An article is "hostile" when the model reads its stance towards the protesters as hostile (the other labels are neutral and sympathetic). Intervals are 95%, from resampling outlets.

| | Italy | other countries | difference |
|---|---|---|---|
| all coverage | 49% (n=1,589) | 19% (n=11,664) | +30.2 points [+18.8, +40.7] |
| own country only | 56% (n=1,233) | 20% (n=6,084) | +35.9 points [+22.1, +48.5] |

Share of sentences about violence: 41% in Italy, 34% elsewhere (+6.8). Share about the demands of the protesters: 19% against 22% (-3.0).

How far to trust it:

- Model A over-calls "hostile" compared with a blind reading of 299 articles by Claude (Anthropic), given title and text without the model labels: 42.0% against 32.5% in Italy (n=200), 19.2% against 11.1% elsewhere (n=99). On the Claude labels the gap is still +20.5 points [+4.8, +35.6].
- Agreement on the stance label, Cohen kappa: 0.64 between model A and the Claude reading (n=299), 0.66 between model A and model B (n=598).
- I removed the country line from the prompt, and swapped it, on 598 articles. The Italian hostile rate moved by +0.3 and -0.3 points, the others by +0.0 and +0.3. The country name in the prompt does not drive the result.
- The outlets differ by country, and the Italian sample has 32 outlets. This and the other limits are in `report/limitations_it.md`.

## Figures

All charts are in `report/charts/` (PNG and SVG, labels in Italian); `report/index.html` shows them with the text around them.

![Share of hostile articles by country](report/charts/c3_paesi.png)

- `c1_ostili_italia_altri`: hostile share, Italy against the other countries
- `c2_violenza_richieste`: share of sentences about violence and about the demands of the protesters
- `c3_paesi` (above): hostile share for the outlets of each country, all coverage and own-country protests only, with 95% intervals
- `c4_settimane`: hostile share week by week, Italy against the rest
- `c5_orientamento`: hostile share by the political leaning of the outlet
- `c6_italia_vs_paese_tutta`, `c6_italia_vs_paese_casa`: Italy against each country, all coverage and own country
- `c6_parole_delegittimanti`: the delegitimising words the model found

## Data

1,439,388 pages were collected from 320 outlets in 49 countries. Two keyword filters and a model label (`protest`, `youth`) kept 18,355 articles about youth protests. 13,253 texts were long enough, not live blogs and not duplicates, and those carry the numbers on the article body. The relevance label was checked on 80 articles for `protest` (73 right) and 40 for `youth` (33 right); it missed 1 of 200 relevant articles.

Each article is labelled twice, from the title alone and from title plus text: stance towards the protesters, main frame, share of violence and demand sentences, who is quoted, delegitimising words. Model A is Qwen3.8-27B (BF16) on all articles. Model B is gpt-oss-120b (MXFP4, as released) on a sample of 600. Temperature 0, 65,536-token window, no prompt cut.

Leaning of the Italian outlets: classification by Luca Bagnariol, with the sourced value kept beside it (`data/leaning_italy.tsv`).

## Not in this repo

The article text. It is copyrighted, so `data/articles/` is not committed; `scrapers/` recreates it. What is here: the code, the labels (`data/framing_*.jsonl` hold URL, outlet and model answer only), the leaning tables with their source quotes, and the report.

## Layout

```
analysis/    labelling (relevance_label.py, framing_label.py), bias_test.py, build_report.py, constants.py
scrapers/    discover.py + fetch_articles.py (recipes), custom/ (one scraper per outlet, 391), polite_fetch.py
grids/       swarm configs and accepted results that produced the recipes and custom scrapers
data/        countries, outlets, leaning, labels
report/      the report, charts, csv
design/      fonts and the style notes used for the charts
```

`PLAN.md` holds the fixed numbers of the study (window, character limits, sample sizes, seeds); `analysis/check_plan.py` compares them with the code and the data.

## Run

```
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
bash scrapers/scrape_all.sh          # recipes: urls, then article text
bash scrapers/scrape_custom.sh       # custom scrapers
python analysis/relevance_label.py PORT MODEL data/relevance_qwen.jsonl   # the three large data files ship as .gz; scripts read either form
python analysis/framing_label.py A data/framing_A.jsonl - 8
export HF_HOME=...                   # framing_label.py reads the tokenizer from the local Hugging Face cache
python analysis/check_plan.py
python analysis/build_report.py
```

The labelling scripts expect an OpenAI-compatible server (vLLM) on the ports listed at the top of each script. `build_report.py` rebuilds everything from the label files; the numbers in the HTML are computed there, not typed.

## State

Report delivered 2026-10-30. Open: no human has labelled a sample yet. The over-calling check rests on the Claude reading of 299 articles; a human-labelled sample would settle how far the absolute rates are off.
