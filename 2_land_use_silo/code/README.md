# code/ — SILO run, validation & performance tooling

All Python tooling for the Updated-SILO stage. Paths are resolved relative to this folder's
parent (`Updated SILO/`), so the scripts read/write `../validation/`, `../calibration/`, etc.

| script | purpose | reads | writes |
|---|---|---|---|
| `collect_yearly_output.py` | copy SILO per-year microdata to the Pipeline output | `silo_smoke_test/scenOutput/<SILO_SCEN>/microData/` | `Pipeline/2_SILO_landuse/output/year_<Y>/` |
| `validate_allstates.py` | per-year, 6-state model-vs-ACS validation engine | scenario microData + ACS PUMS | `../validation/<OUT_SUB>/…/summary.csv` |
| `compute_floors.py` | identifiability floors (ACS bootstrap) | ACS PUMS (via validate_allstates) | `../validation/floors_<year>.csv` |
| `performance_scorecard.py` | forecast TV vs floor vs baseline + verdicts | `../validation/{floors,summary,baseline}.csv` | `../validation/scorecard_*.csv` |
| `make_performance_figures.py` | the figure suite | `../validation/*summary.csv` | `../validation/figures/*.png` |
| `report_calib_forecast.py` | quick calib-vs-forecast text report | `../validation/*summary.csv` | stdout |

Env vars: `SILO_SCEN` (scenario name under `scenOutput/`), `OUT_SUB` (validation output subfolder).

## Method: calibrate → forecast → validate
SILO is scored as a forecasting model. Behavioral coefficients + control totals are calibrated
ONCE on **2016–2020** (actual ACS), then frozen and used to **forecast 2021–2023** (blind to
actual ACS). In-sample fit (2016–2020) confirms tracking; **out-of-sample skill (2021–2023)** is
the headline number.

## Metrics
Per state × variable × year: **Total Variation (TV)** of the marginal (target TV < 0.05),
**income median bias %**, and mean TV across the 8 core variables (hhSize, autos, dwellingType,
hh_inc9, age_bin, gender, race4, occ_silo). Forecast **skill = 1 − TV_model/TV_baseline**.
Verdicts: EXCELLENT (TV ≤ 1.5×floor), GOOD (<0.05), FAIR (<0.10), POOR (≥0.10).
The **identifiability floor** is the irreducible TV from ACS sampling noise (survey bootstrap);
observed TV ≤ floor means "as accurate as the data allows" (computed floors are 0.5–2.1%).
