#!/usr/bin/env python3
"""Per-bin acceptance scorecard: SILO vs ACS, max |share_SILO - share_ACS| over the bins of each
variable (the headline criterion is each bin within +/-5 percentage points, NOT aggregate TV).

For every (year, state, variable) it computes the largest single-category share gap in percentage
points; a (state, variable) passes the forecast test when its worst bin over 2021-2023 is < 5 pp.

Usage:
  SILO_SCEN=updated_vae_calib2 python perbin_scorecard.py 2016 2017 2018 2019 2020 2021 2022 2023
Writes ../validation/<OUT_SUB or by_year_acs_<scen>>/perbin_scorecard.csv  (+ prints a summary).
"""
from __future__ import annotations
import os, sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
SMOKE = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test")
SCEN = os.environ.get("SILO_SCEN", "updated_vae_calib2")
TOL = 5.0   # percentage-point per-bin tolerance

import valib as V
V.SCEN = SMOKE / "scenOutput" / SCEN / "microData"
spec = importlib.util.spec_from_file_location("va", HERE / "validate_allstates.py")
va = importlib.util.module_from_spec(spec); spec.loader.exec_module(va)

STATES = ["MD", "VA", "PA", "DE", "DC", "WV"]
HH_BINS = {"hhSize": list(range(1, 8)), "autos": list(range(0, 4)),
           "dwellingType": list(range(1, 6)), "hh_inc9": list(range(0, 9))}
PP_BINS = {"age_bin": list(range(0, 18)), "gender": [1, 2],
           "occ_silo": list(range(0, 5)), "race4": ["white", "black", "hispanic", "other"]}
VAR_ORDER = ["hhSize", "autos", "dwellingType", "hh_inc9", "age_bin", "gender", "occ_silo", "race4"]


def share(vals, w, cats):
    d = np.zeros(len(cats)); idx = {c: i for i, c in enumerate(cats)}
    for v, wt in zip(vals, w):
        if v in idx:
            d[idx[v]] += wt
    s = d.sum()
    return d / s if s > 0 else d


def main(years):
    rows = []
    for yr in years:
        try:
            sh, sp = V.load_silo_year(yr); rh, rp = va.load_acs6(yr)
        except FileNotFoundError:
            print(f"skip {yr}: no SILO output"); continue
        for st in STATES:
            shs, rhs = sh[sh.state == st], rh[rh.state == st]
            sps, rps = sp[sp.state == st], rp[rp.state == st]
            if len(rhs) == 0 or len(shs) == 0:
                continue                                  # partial state skipped this year
            for var, cats in HH_BINS.items():
                gap = np.abs(share(shs[var], shs.w, cats) - share(rhs[var], rhs.w, cats)) * 100
                rows.append((yr, st, var, round(float(gap.max()), 1)))
            for var, cats in PP_BINS.items():
                gap = np.abs(share(sps[var], sps.w, cats) - share(rps[var], rps.w, cats)) * 100
                rows.append((yr, st, var, round(float(gap.max()), 1)))

    df = pd.DataFrame(rows, columns=["year", "state", "variable", "max_bin_pp"])
    out = V.SCEN.parent.name  # scenario
    outdir = HERE.parent / "validation" / os.environ.get("OUT_SUB", f"by_year_acs_{SCEN.replace('updated_vae_', '')}")
    outdir.mkdir(parents=True, exist_ok=True)
    df.to_csv(outdir / "perbin_scorecard.csv", index=False)

    fc = df[df.year.between(2021, 2023)].groupby(["state", "variable"]).max_bin_pp.max().unstack()
    fc = fc.reindex(index=[s for s in STATES if s in fc.index], columns=[v for v in VAR_ORDER if v in fc.columns])
    print(f"\n=== {SCEN}: worst per-bin gap (pp), forecast 2021-2023 ===")
    print(fc.to_string())
    fail = df[(df.year.between(2021, 2023)) & (df.max_bin_pp >= TOL)]
    n_cells = len(df[df.year.between(2021, 2023)].groupby(["state", "variable"]))
    n_fail = len(fc.stack()[fc.stack() >= TOL]) if not fc.empty else 0
    print(f"\nForecast (state x variable) cells failing per-bin {TOL}pp: {n_fail} / {n_cells}")
    if not fail.empty:
        print("by variable:", fail.groupby("variable").size().to_dict())
    print(f"\n-> {outdir / 'perbin_scorecard.csv'}")
    return df


if __name__ == "__main__":
    yrs = [int(a) for a in sys.argv[1:]] or list(range(2016, 2024))
    main(yrs)
