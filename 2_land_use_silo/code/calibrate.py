#!/usr/bin/env python3
"""Approach-B calibration controller: propose per-state behavioural levers from the gap between a
SILO run and ACS at the end of the calibration window, then (optionally) write the frozen
calibration_by_state.csv. Iterate: run SILO -> calibrate --apply -> run SILO -> ... until the
2016-2020 fit converges; then freeze and forecast 2021-2023.

Levers (each defaults to no-op; damped proportional update toward the ACS target, with deadband):
  incomeGrowth  <- household income median ratio (applied per year; corrected over n years)
  autoScaler    <- mean autos per household ratio  (prob. of owning a car)
  birthScaler   <- mean household size ratio       (more births -> larger households)
  marriageScaler<- single-person-household share   (more marriage -> fewer 1-person households)

Usage:
  python calibrate.py                 # dry-run: print current gaps + proposed levers (no write)
  python calibrate.py --apply         # write calibration_by_state.csv with the proposed values
  env SILO_SCEN=updated_vae_fcast CALIB_YEAR=2020 python calibrate.py [--apply]
"""
from __future__ import annotations
import os, sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
CALIB_CSV = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/input/assumptions/calibration_by_state.csv")
CALIB_YEAR = int(os.environ.get("CALIB_YEAR", "2020"))
BASE_YEAR = 2016
NYEARS = max(1, CALIB_YEAR - BASE_YEAR)
DAMP = float(os.environ.get("CALIB_DAMP", "0.6"))      # 0..1 step fraction toward target
DEADBAND = 0.01                                         # ignore |ratio-1| below this
STATES = ["DE", "DC", "MD", "PA", "VA", "WV"]
FIPS = {"DE": 10, "DC": 11, "MD": 24, "PA": 42, "VA": 51, "WV": 54}

import valib as V
V.SCEN = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/scenOutput") / \
         os.environ.get("SILO_SCEN", "updated_vae_fcast") / "microData"
# ACS loader from the validator
spec = importlib.util.spec_from_file_location("va", HERE / "validate_allstates.py")
va = importlib.util.module_from_spec(spec); spec.loader.exec_module(va)


def wmean(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float); s = w.sum()
    return float((x * w).sum() / s) if s > 0 else float("nan")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main(apply: bool):
    cur = pd.read_csv(CALIB_CSV)
    cur = cur.set_index("state")
    sh, sp = V.load_silo_year(CALIB_YEAR)
    rh, rp = va.load_acs6(CALIB_YEAR)

    rows = []
    for st in STATES:
        shs, rhs = sh[sh.state == st], rh[rh.state == st]
        if len(shs) == 0 or len(rhs) == 0:
            rows.append(cur.loc[st].to_dict() | {"state": st}); continue
        # targets at CALIB_YEAR
        s_auto, a_auto = wmean(shs.autos, shs.w), wmean(rhs.autos, rhs.w)
        s_hh, a_hh = wmean(shs.hhSize, shs.w), wmean(rhs.hhSize, rhs.w)
        s_single = wmean((shs.hhSize == 1).astype(float), shs.w)
        a_single = wmean((rhs.hhSize == 1).astype(float), rhs.w)
        s_inc = V.wq(shs.income.to_numpy(float), shs.w.to_numpy(float), [.5])[0]
        a_inc = V.wq(rhs.income.to_numpy(float), rhs.w.to_numpy(float), [.5])[0]

        b = float(cur.loc[st, "birthScaler"]); m = float(cur.loc[st, "marriageScaler"])
        g = float(cur.loc[st, "incomeGrowth"]); au = float(cur.loc[st, "autoScaler"])

        # --- proposed updates (damped, with deadband) ---
        r_auto = a_auto / s_auto if s_auto > 0 else 1.0
        if abs(r_auto - 1) > DEADBAND:
            au = clamp(au * (1 + DAMP * (r_auto - 1)), 0.4, 2.5)
        r_hh = a_hh / s_hh if s_hh > 0 else 1.0
        if abs(r_hh - 1) > DEADBAND:
            b = clamp(b * (1 + DAMP * (r_hh - 1)), 0.3, 3.0)
        # singles: more ACS singles than SILO -> reduce marriage
        if a_single > 0 and abs(s_single - a_single) / a_single > DEADBAND:
            m = clamp(m * (1 + DAMP * ((s_single - a_single) / a_single)), 0.3, 3.0)
        # income: correct the median ratio spread over the n calibration years
        r_inc = a_inc / s_inc if s_inc > 0 else 1.0
        if abs(r_inc - 1) > DEADBAND:
            g = clamp(g * (r_inc ** (DAMP / NYEARS)), 0.95, 1.10)

        rows.append({"STFIPS": FIPS[st], "state": st,
                     "birthScaler": round(b, 4), "marriageScaler": round(m, 4),
                     "incomeGrowth": round(g, 4), "autoScaler": round(au, 4)})
        print(f"{st}: autos SILO {s_auto:.3f} vs ACS {a_auto:.3f} (x{r_auto:.3f}) -> autoScaler {au:.3f} | "
              f"hhSize {s_hh:.3f}/{a_hh:.3f} -> birth {b:.3f} | "
              f"single {s_single:.3f}/{a_single:.3f} -> marr {m:.3f} | "
              f"inc {s_inc:,.0f}/{a_inc:,.0f} (x{r_inc:.3f}) -> growth {g:.4f}")

    out = pd.DataFrame(rows)[["STFIPS", "state", "birthScaler", "marriageScaler", "incomeGrowth", "autoScaler"]]
    print("\n=== proposed calibration_by_state.csv ===")
    print(out.to_string(index=False))
    if apply:
        out.to_csv(CALIB_CSV, index=False)
        print(f"\nWROTE {CALIB_CSV}")
    else:
        print("\n(dry-run; re-run with --apply to write)")


if __name__ == "__main__":
    main("--apply" in sys.argv)
