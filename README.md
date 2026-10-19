# Carbon- and PUE-Aware Scheduling of Consumer-Electronics Cloud Workloads

This folder reproduces **every figure, table and number** in the article from public data with one command. Everything runs on a CPU in a few minutes. No GPU, account or API key is needed.

---

## Contents

1. [What the study does](#1-what-the-study-does)
2. [Quick start](#2-quick-start)
3. [Folder structure](#3-folder-structure)
4. [Data sources](#4-data-sources)
5. [Method](#5-method)
6. [Scheduling strategies compared](#6-scheduling-strategies-compared)
7. [Configuration (`config/params.yaml`)](#7-configuration-configparamsyaml)
8. [Running individual steps](#8-running-individual-steps)
9. [Runtime and energy footprint](#9-runtime-and-energy-footprint)

---

## 1. What the study does

Smartphones, wearables, smart speakers and other consumer devices rely on cloud back-ends that run in data centers. A large part of this cloud work does not have to run the moment it arrives:

| Workload | Can it wait? | Can it move to another region? |
|---|---|---|
| Voice-assistant serving | No (interactive) | No (latency) |
| Photo/video backup AI indexing | Up to 24 h | Yes |
| OTA firmware build and delta packaging | Up to 12 h | Yes |
| On-device AI model retraining | Up to 48 h | Yes |

The code simulates a hypothetical consumer-electronics (CE) cloud back-end with an average IT load of 1 MW. It runs for every hour of 2025 across **nine European data-center regions** (IE, UK, NL, BE, DK, FI, DE, FR, PL). It then asks how much CO2e a scheduler saves by choosing:

- **when** a job runs (temporal shifting to cleaner hours),
- **where** it runs (spatial shifting to cleaner grids or more efficient sites),
- or both,

while respecting each job's deadline and each region's spare capacity. Emissions are computed as

```
emissions = IT energy x PUE(region) x grid carbon intensity(region, hour)   [gCO2e]
```

plus a migration overhead for jobs that leave their home region.

Main result (users in Germany, persistence forecast): spatio-temporal scheduling cuts whole-fleet emissions by **58.8%** against running everything immediately in Germany. The perfect-forecast bound is 59.7%. Almost all of the gain comes from choosing the region. The exact values are always the ones in `outputs/results.json` and `latex/numbers.tex`.

---

## 2. Quick start

Requirements: **Python 3.10 or newer** (tested with 3.12) on Windows, Linux or macOS.

```bash
cd code
python -m pip install -r requirements.txt
python src/run_all.py
```

That is all. The script:

1. reuses the cached data in `data/`, or downloads it if missing,
2. runs all simulations,
3. writes `outputs/results.json`,
4. writes the LaTeX tables and number macros to `../latex/tables/` and `../latex/numbers.tex`,
5. writes the four figures to `../latex/figures/` (300 dpi PNG and vector PDF).

It prints `run_all finished in N s` when done.

Optional virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
python -m pip install -r requirements.txt
```

### Dependencies (`requirements.txt`)

| Package | Used for |
|---|---|
| numpy, pandas | data handling and simulation |
| matplotlib | figures |
| pyyaml | reading `config/params.yaml` |
| python-docx, python-pptx | only for building the Word article and figure deck (`make_word.py`) |

`fetch_data.py` uses only the Python standard library for HTTP, so no extra package is needed to download data.

---

## 3. Folder structure

```
code/
├── README.md                  this file
├── requirements.txt           Python dependencies
├── config/
│   └── params.yaml            ALL parameters: regions, PUE, emission factors, workloads, sensitivity ranges
├── data/                      cached public input data (reduced to hourly UTC)
│   ├── SOURCES.md             source, URL, licence and access date of every file
│   ├── ACCESS_LOG.txt         log of download requests
│   ├── energycharts_public_power_<cc>_2025_hourly.csv.gz   generation by source, 9 countries
│   ├── neso_gb_carbon_intensity_2025_hourly.csv            UK carbon intensity (NESO)
│   └── energinet_dk_co2emis_2025_hourly.csv                Danish cross-check (Energinet)
├── src/
│   ├── run_all.py             single entry point (fetch, analysis, tables, figures)
│   ├── common.py              paths and config loader
│   ├── fetch_data.py          downloads and caches the public data
│   ├── carbon.py              generation mix -> hourly carbon intensity
│   ├── scheduler.py           greedy online scheduler and emission accounting
│   ├── analysis.py            all experiments (parallel) -> outputs/results.json
│   ├── tables.py              LaTeX tables and number macros
│   ├── figures.py             Fig. 1 to Fig. 4
│   └── make_word.py           builds word/paper.docx and the figure deck from latex/main.tex
└── outputs/
    ├── results.json                                   every result used in the article
    └── hourly_carbon_intensity_gco2e_per_kwh.csv.gz   hourly CI, 9 regions x 8,760 h
```

---

## 4. Data sources

All data is public and needs no login. Full details, including request URLs and licences, are in [`data/SOURCES.md`](data/SOURCES.md). Data was accessed on 2026-10-18.

| Data | Source | Used for |
|---|---|---|
| Hourly net public generation by production type, 2025 | Energy-Charts API, Fraunhofer ISE (CC BY 4.0) | Carbon intensity for IE, NL, BE, DK, FI, DE, FR, PL |
| Hourly GB carbon intensity, 2025 | NESO Carbon Intensity API | Carbon intensity for the UK |
| Hourly CO2 per kWh consumed, DK1/DK2 | Energinet Energi Data Service | Cross-check of the Danish series only |
| Per-campus PUE, Q4 2025 | Google "Data center efficiency" page | PUE for IE 1.08, NL 1.07, BE 1.08, DK 1.07, FI 1.10 |
| Industry average PUE (1.54) | Uptime Institute 2025 survey, as quoted on the Google page | PUE for UK, DE, FR, PL (assumed colocation) |
| Life-cycle emission factors (min / median / max) | IPCC AR5 WGIII Annex III, Table A.III.2 | gCO2e per kWh for each production type |

The cached files in `data/` total about 3 MB. If they are deleted, `fetch_data.py` downloads them again. Energy-Charts allows about 2 requests per minute, so a fresh download takes about 7 extra minutes.

---

## 5. Method

### 5.1 Hourly carbon intensity (`carbon.py`)

For each country and hour, the carbon intensity is the generation-weighted average of the life-cycle emission factors:

```
CI(t) = sum_s  G_s(t) x EF_s  /  sum_s G_s(t)        [gCO2e/kWh]
```

- `G_s(t)`: generation of source `s` (MW) from Energy-Charts
- `EF_s`: IPCC AR5 median factor; `min` and `max` are used in the sensitivity analysis

Storage discharge (pumped hydro, batteries) and non-generation series (load, trade, shares) are excluded to avoid double counting. Small gaps (at most 20 of 8,760 hours) are filled by time interpolation. The UK uses the NESO series directly, because the Energy-Charts UK series is incomplete.

### 5.2 Workload arrivals (`scheduler.arrivals`)

Every hour, each workload class releases one aggregate job. Its energy equals the class's share of the fleet energy, times an hourly arrival profile in local time:

- **user**: follows daily user activity (voice)
- **night**: peaks while phones charge on Wi-Fi at night (photo upload)
- **flat**: constant (OTA builds, retraining)

### 5.3 Scheduler (`scheduler.simulate`)

A **greedy online scheduler** processes hours in order:

1. For each new job it lists all feasible options (region, start hour) inside the job's deadline window. Only the home region is allowed if the job is not spatially movable.
2. It ranks the options by forecast cost, `forecast CI x PUE x energy`, plus the migration overhead for non-home regions.
   - **persistence** forecast: the same hour on the previous day (realistic and simple)
   - **oracle** forecast: the true future values (an upper bound on savings)
3. It fills the cheapest options first, up to a **per-region headroom**: the maximum deferrable load one region may absorb in an hour.
4. Any energy that cannot be placed runs in the home region before its deadline.
5. Emissions are always booked with the **true** CI and PUE, never the forecast.

### 5.4 Metrics

For each class and for the whole fleet the simulation reports:

- emissions (tCO2e)
- energy (MWh, including PUE and migration overhead)
- share of deferrable energy that was moved
- mean delay (h)
- overflow (energy that missed a cheap slot)
- regional share of the deferrable work

Savings are reported as a percentage against the **baseline**, in which every job runs immediately in the home region.

---

## 6. Scheduling strategies compared

| Strategy (`strategy=`) | Time shifting | Region shifting | Planner sees | Purpose |
|---|---|---|---|---|
| `baseline` | no | no | nothing | reference: run now, at home |
| `temporal` | yes | no | CI x PUE | wait for cleaner hours at home |
| `spatial` | no | yes | CI x PUE | move now to the cleanest region |
| `spatiotemporal` | yes | yes | CI x PUE | proposed carbon- and PUE-aware scheduler |
| `pue_blind` | yes | yes | CI only | shows the value of knowing PUE |
| `lowest_pue` | no | yes | PUE only | "pick the most efficient site" heuristic |

`lowest_pue` and tied sites: NL and DK both have PUE 1.07. By default (`tie="split"`) the work is split equally between the tied sites. The article also reports the all-NL and all-DK cases (`lowest_pue_tie` in `results.json`), because the result depends strongly on which site wins the tie.

---

## 7. Configuration (`config/params.yaml`)

Every parameter of the study lives in this one file. Each value either cites a public source or is marked **ASSUMPTION**. Every assumption is varied in the sensitivity analysis.

| Section | What it controls |
|---|---|
| `study` | year (2025), home region (`DE`), fleet IT load (1 MW), forecast type, migration overhead (5%), headroom factor (1.5) |
| `regions` | the nine regions, their Energy-Charts country code and their PUE with its source |
| `emission_factors` | IPCC life-cycle factors (median / min / max) per production type |
| `storage_types`, `non_generation` | series excluded from the carbon intensity |
| `workloads` | per class: energy share, deadline window (h), job duration (h), whether it may move region, arrival profile |
| `profiles` | 24-hour arrival shapes (`user`, `night`, `flat`) |
| `sensitivity` | ranges for window scale, headroom, migration overhead, emission-factor set, PUE scenario, arrival profile |

Examples of changes:

```yaml
study:
  home_region: FR          # users served from France instead of Germany
  forecast: oracle         # perfect-foresight bound
workloads:
  photo:
    spatial: false         # keep photos in the home country (data residency)
```

After editing, rerun `python src/run_all.py`. Results are reported as percentages, so they do not depend on the absolute 1 MW load. They do depend on the workload mix, windows and durations.

---

## 8. Running individual steps

All scripts are run from the `code/` folder.

```bash
python src/fetch_data.py     # download or verify cached data only
python src/analysis.py       # simulations -> outputs/results.json
python src/tables.py         # tables + numbers.tex from results.json
python src/figures.py        # figures from results.json and hourly CI
```

`tables.py` and `figures.py` only read `results.json`. After changing a figure's style you therefore do not need to rerun the simulations.

Calling the scheduler directly from Python:

```python
import sys; sys.path.insert(0, "src")
from common import load_cfg
from carbon import ci_matrix
from scheduler import simulate, savings

cfg = load_cfg()
ci, info = ci_matrix(cfg)                              # DataFrame (hours x regions), gap info
pue = [r["pue"] for r in cfg["regions"]]
base = simulate(ci, pue, "DE", cfg, strategy="baseline")
st   = simulate(ci, pue, "DE", cfg, strategy="spatiotemporal", forecast="persistence")
print(savings(base, st))                               # percent saving
```

---

## 9. Runtime and energy footprint

- The full `run_all.py` takes about **2 to 5 minutes** on an 8-core laptop CPU. The last recorded run took 261 s for about 100 one-year hourly simulations, run in parallel with `multiprocessing`.
- Downloads total about 45 MB of raw API responses, reduced to about 3 MB stored. This happens only on the first run.
- No GPU and no model training are used. This keeps the study's own footprint small, in line with its topic.
