#!/usr/bin/env python3
"""Collect the SILO per-year microdata into the Pipeline land-use output folder.

SILO writes hh/pp/dd/jj_<year>.csv into
  silo_smoke_test/scenOutput/<SILO_SCEN>/microData/
This copies each simulated year's four files into
  Pipeline/2_SILO_landuse/output/year_<year>/{hh,pp,dd,jj}_<year>.csv
(the MITO input location) plus the per-year aggregate result CSVs and a manifest.

Env: SILO_SCEN (default 'updated_vae_fcast') selects the scenario to collect.
"""
from __future__ import annotations
import os, shutil
from pathlib import Path
import pandas as pd

SMOKE = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test")
SCEN = SMOKE / "scenOutput" / os.environ.get("SILO_SCEN", "updated_vae_fcast")
MD = SCEN / "microData"
HERE = Path(__file__).resolve().parent
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Pipeline/2_SILO_landuse/output")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for year in range(2016, 2024):
        yd = OUT / f"year_{year}"; yd.mkdir(parents=True, exist_ok=True)
        rec = {"year": year}
        for tag in ("hh", "pp", "dd", "jj"):
            src = MD / f"{tag}_{year}.csv"
            if src.exists():
                dst = yd / f"{tag}_{year}.csv"
                shutil.copy2(src, dst)
                # count rows cheaply
                with open(src) as f:
                    n = sum(1 for _ in f) - 1
                rec[tag] = n
            else:
                rec[tag] = None
        rows.append(rec)
        print(f"{year}: " + ", ".join(f"{k}={rec.get(k)}" for k in ("hh","pp","dd","jj")))
    # aggregate time-series summaries from siloResults
    sr = SCEN / "siloResults"
    if sr.exists():
        dst = OUT / "siloResults"
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(sr, dst)
        print(f"copied aggregate summaries -> {dst}")
    for extra in ("resultFile.csv", "resultFileSpatial.csv"):
        p = SCEN / extra
        if p.exists(): shutil.copy2(p, OUT / extra)
    pd.DataFrame(rows).to_csv(OUT / "manifest.csv", index=False)
    print(f"\n-> {OUT}")

if __name__ == "__main__":
    raise SystemExit(main())
