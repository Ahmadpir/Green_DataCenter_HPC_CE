# Code: carbon- and PUE-aware scheduling of consumer-electronics cloud workloads

Reproduces every figure, table and number of the article (P06, IEEE CEM special issue).

## Run
```bash
python -m pip install -r requirements.txt
python src/run_all.py
```
Python 3.12, CPU only. With the cached data in `data/` a full run takes about 2-5 minutes on an
8-core laptop (93 one-year hourly simulations in parallel). Without the cache, `fetch_data.py`
first downloads about 3 MB of reduced data (raw API responses are about 45 MB in total and are
not stored); Energy-Charts allows 2 requests per minute, so the first run takes about 7 minutes longer.

## What it does
1. `fetch_data.py` downloads and caches public data (see `data/SOURCES.md`).
2. `carbon.py` turns hourly generation by source into life-cycle carbon intensity (IPCC AR5 factors).
3. `scheduler.py` is a greedy online scheduler: every hour each workload class releases an aggregate
   job (energy, duration, deadline window, allowed regions); the scheduler ranks (region, start)
   options by forecast CI x PUE x energy (day-ahead persistence forecast, or perfect foresight as a
   bound), fills them under a per-region headroom and runs leftovers at home before the deadline.
4. `analysis.py` runs the main comparison, every region as home, and the sensitivity analysis
   -> `outputs/results.json`, `outputs/hourly_carbon_intensity_gco2e_per_kwh.csv.gz`.
5. `tables.py` writes `latex/tables/*.tex` and `latex/numbers.tex` (macros used in the text).
6. `figures.py` writes `latex/figures/fig1..fig4` (PNG 300 dpi + PDF).

All assumptions (workload mix, windows, durations, arrival profiles, headroom, migration
overhead) are in `config/params.yaml` and labelled ASSUMPTION; the sensitivity ranges are there too.

## Word / PowerPoint
`python src/make_word.py` builds `word/paper.docx` and `word/figures_for_submission.pptx`
from `latex/main.tex` after the LaTeX build.
