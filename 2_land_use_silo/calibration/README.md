# Calibration (2016–2020 window)

Approach B: behavioral coefficients are calibrated **once** on the 2016–2020 backcast (where ACS
is observed), then **frozen** and used to forecast 2021–2023. This folder holds the calibration
inputs and the resulting calibrated values; nothing here is re-fit per forecast year.

What lives here:
- **Control totals & targets** used during the calibration window (population by state, employment
  forecast, migration marginals) — the exogenous steering for 2016–2020.
- **Calibrated coefficients** (frozen): per-state birth/marriage scalers, per-state income
  real-growth rate, per-region auto-ownership income response.
- **Calibration summary** — in-sample fit (2016–2020 mean TV) per state/variable, confirming the
  model can track when calibrated.

Out-of-sample forecast skill (2021–2023) is scored in `../validation/` against actual ACS.
