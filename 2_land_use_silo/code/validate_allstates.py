#!/usr/bin/env python3
"""6-state per-year validation: SILO vs ACS PUMS 5-yr for DE/DC/MD/PA/VA/WV.

Unlike the 3-state validator, the partial states (PA/VA/WV — only some PUMAs are inside the
MSTM region) are handled by filtering ACS to the in-region PUMAs (from the VAE puma list) and
weighting each ACS record by its PUMA's coverage fraction, so the ACS sample matches the
in-region population SILO actually simulates. MD/DC/DE are fully in-region (coverage 1.0), so
they reproduce the 3-state results.

Usage: python validate_allstates.py 2016 2017 2018 2019 2020 2021
Writes to Updated SILO/validation/by_year_acs_allstates/<year>/<state>/ + summary.csv
"""
from __future__ import annotations
import sys, json, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

DEL = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
SMOKE = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test")
HERE = Path(__file__).resolve().parent
UV = DEL / "Updated VAE"

import valib as m                       # rebuilt self-contained validation library (see code/valib.py)
v = m
import os
m.SCEN = SMOKE / "scenOutput" / os.environ.get("SILO_SCEN","updated_vae_fcast") / "microData"
m.OUT = HERE.parent / "validation" / os.environ.get("OUT_SUB","by_year_acs_fcast")
STATES6 = {10: "DE", 11: "DC", 24: "MD", 42: "PA", 51: "VA", 54: "WV"}
m.STATES = STATES6

MSTM = set(json.load(open(UV / "outputs/02_targets/puma_to_idx.json")).keys())
COV = json.load(open(UV / "inputs/coverage_fractions.json"))
CPI = m.CPI


def pkey(stfips, puma):
    return f"{int(stfips)}_{str(puma).strip().zfill(5)}"


# MD/DC/DE are fully inside the MSTM region (whole state) -> no PUMA filter needed.
# PA/VA/WV are partial -> filter to in-region PUMAs + coverage-weight. The 2010-PUMA
# in-region list matches the "PUMA" column (<=2021) or "PUMA10" (2022); 2023 PUMS uses
# 2020 PUMAs ("PUMA") which won't match -> those partial states are skipped that year.
FULL_STATES = {24, 11, 10}

def load_acs6(year):
    pdir = m.pums_dir(year); defl = CPI[2016] / CPI[year]
    hh_l, pp_l = [], []
    for fips, ab in STATES6.items():
        h = v.read_pums_zip(pdir / f"csv_h{ab.lower()}.zip",
                            ["SERIALNO", "PUMA", "PUMA10", "WGTP", "NP", "VEH", "HINCP", "ADJINC", "BLD", "TYPE", "TYPEHUGQ"])
        tcol = "TYPEHUGQ" if "TYPEHUGQ" in h.columns else "TYPE"
        h = h[(pd.to_numeric(h[tcol], errors="coerce") == 1) & (pd.to_numeric(h["NP"], errors="coerce") >= 1)].copy()
        if fips in FULL_STATES:
            h["cov"] = 1.0                                              # whole state in-region
        else:
            # The in-region list is keyed by 2010 PUMAs. PUMS <=2021 carries 2010 codes in "PUMA";
            # 2022 carries them in "PUMA10"; 2023 5-yr switched to 2020 PUMAs ("PUMA", no "PUMA10").
            # 2020-vintage codes partially collide with 2010 numbers, so a naive filter keeps the
            # WRONG sub-sample (corrupting the comparison) instead of cleanly failing. Detect the
            # vintage and skip partial states when no 2010-keyed column is available, rather than
            # validating against a mis-filtered ACS slice.
            has_2010 = ("PUMA10" in h.columns) or (year <= 2021)
            if not has_2010:
                print(f"    (skip {ab} {year}: PUMS uses 2020 PUMAs; no 2010 in-region crosswalk -> "
                      f"partial state not validated this year)"); continue
            pcol = "PUMA10" if "PUMA10" in h.columns else "PUMA"        # 2010-PUMA column
            h["puma_key"] = [pkey(fips, p) for p in h[pcol]]
            h = h[h["puma_key"].isin(MSTM)].copy()                      # in-region PUMAs only
            if len(h) == 0:                                            # nothing matched -> skip
                print(f"    (skip {ab} {year}: PUMA codes don't match 2010 in-region list)"); continue
            h["cov"] = h["puma_key"].map(COV).fillna(1.0).astype(float)
        h["state"] = ab
        p = v.read_pums_zip(pdir / f"csv_p{ab.lower()}.zip",
                            ["SERIALNO", "PWGTP", "AGEP", "SEX", "RAC1P", "HISP", "ESR", "SCHG", "PINCP", "ADJINC"])
        p = p[p["SERIALNO"].isin(set(h["SERIALNO"]))].copy()
        p = p.merge(h[["SERIALNO", "cov"]], on="SERIALNO", how="left"); p["state"] = ab
        hh_l.append(h); pp_l.append(p)
    hh = pd.concat(hh_l, ignore_index=True); pp = pd.concat(pp_l, ignore_index=True)
    adj = pd.to_numeric(hh["ADJINC"], errors="coerce").fillna(1e6)
    hh["income"] = pd.to_numeric(hh["HINCP"], errors="coerce").fillna(0) * adj / 1e6 * defl
    hh["hhSize"] = pd.to_numeric(hh["NP"], errors="coerce").clip(1, 7)
    hh["autos"] = pd.to_numeric(hh["VEH"], errors="coerce").fillna(0).clip(0, 3).astype(int)
    hh["dwellingType"] = pd.to_numeric(hh["BLD"], errors="coerce").fillna(2).astype(int).map(v.BLD_TO_TYPE).fillna(1).astype(int)
    hh["hh_inc9"] = pd.cut(hh["income"].astype(float), v.HH_INC_CUTS, labels=False, right=True).astype(int)
    hh["w"] = pd.to_numeric(hh["WGTP"], errors="coerce").fillna(0).clip(lower=0) * hh["cov"]   # coverage-weighted
    adj = pd.to_numeric(pp["ADJINC"], errors="coerce").fillna(1e6)
    pp["income"] = pd.to_numeric(pp["PINCP"], errors="coerce").fillna(0) * adj / 1e6 * defl
    pp["age"] = pd.to_numeric(pp["AGEP"], errors="coerce").clip(0, 99)
    pp["age_bin"] = (pp["age"] // 5).clip(0, 17).astype(int)
    pp["gender"] = pd.to_numeric(pp["SEX"], errors="coerce").clip(1, 2).astype(int)
    rac = pd.to_numeric(pp["RAC1P"], errors="coerce").fillna(1).astype(int)
    hisp = pd.to_numeric(pp["HISP"], errors="coerce").fillna(1).astype(int)
    pp["race4"] = np.select([hisp > 1, rac == 1, rac == 2], ["hispanic", "white", "black"], default="other")
    esr = pd.to_numeric(pp["ESR"], errors="coerce").fillna(6).astype(int)
    schg = pd.to_numeric(pp["SCHG"], errors="coerce").fillna(0).astype(int); age = pp["age"].to_numpy()
    pp["occ_silo"] = np.select([age < 6, np.isin(esr, [1, 2, 4, 5]), schg > 0, esr == 3, (age >= 62) & (esr == 6)],
                               [0, 1, 3, 2, 4], default=2)
    pp["w"] = pd.to_numeric(pp["PWGTP"], errors="coerce").fillna(0).clip(lower=0) * pp["cov"].fillna(1.0)
    return hh, pp


def main(years):
    m.OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for year in years:
        pdir = m.pums_dir(year)
        need = [f"csv_{hp}{st}.zip" for st in [s.lower() for s in STATES6.values()] for hp in ("h", "p")]
        if any(not (pdir / f).exists() or (pdir / f).stat().st_size < 1000 for f in need):
            print(f"SKIP {year}: PUMS missing"); continue
        print(f"=== {year}: loading ACS(6 states, PUMA-filtered) + SILO ===", flush=True)
        rh, rp = load_acs6(year); sh, sp = m.load_silo_year(year)
        for fips, st in STATES6.items():
            d = m.OUT / str(year) / st; d.mkdir(parents=True, exist_ok=True)
            rhs, shs = rh[rh.state == st], sh[sh.state == st]
            rps, sps = rp[rp.state == st], sp[sp.state == st]
            if len(rhs) == 0 or len(shs) == 0:
                print(f"  {year} {st}: no data (ACS {len(rhs)}, SILO {len(shs)})"); continue
            tvs = {}
            for var, ttl in m.HH_VARS:
                tvs[var] = m.one_var_fig(d / f"hh_{var}.png", var, ttl, year, shs[var], shs.w, rhs[var], rhs.w)
            for var, ttl in m.PP_VARS:
                if var not in sps.columns or var not in rps.columns:
                    continue                          # e.g. race4 absent in pre-race SILO output
                tvs[var] = m.one_var_fig(d / f"pp_{var}.png", var, ttl, year, sps[var], sps.w, rps[var], rps.w)
            mb = 100 * (np.median(shs.income) - v.wq(rhs.income.to_numpy(float), rhs.w.to_numpy(float), [.5])[0]) \
                 / max(1.0, v.wq(rhs.income.to_numpy(float), rhs.w.to_numpy(float), [.5])[0])
            for var, tv in tvs.items():
                summary.append({"year": year, "state": st, "variable": var, "tv": round(tv, 4)})
            summary.append({"year": year, "state": st, "variable": "income_median_bias_pct", "tv": round(float(mb), 2)})
            pd.DataFrame([s for s in summary if s["year"] == year and s["state"] == st]).to_csv(
                d.parent / f"metrics_{st}.csv", index=False)
            print(f"  {year} {st} (n_hh ACS={len(rhs):,} SILO={len(shs):,}): "
                  + " ".join(f"{k}={tvs[k]:.3f}" for k in tvs) + f" inc_bias={mb:+.1f}%", flush=True)
    sf = m.OUT / "summary.csv"
    allr = pd.DataFrame(summary)
    if sf.exists():
        prev = pd.read_csv(sf); prev = prev[~prev.year.isin(years)]
        allr = pd.concat([prev, allr], ignore_index=True)
    allr.sort_values(["year", "state", "variable"]).to_csv(sf, index=False)
    print(f"\n-> {m.OUT}")


if __name__ == "__main__":
    yrs = [int(a) for a in sys.argv[1:]] or list(range(2016, 2022))
    main(yrs)
