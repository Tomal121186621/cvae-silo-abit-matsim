#!/usr/bin/env python3
"""STEP 01 — recode raw ACS PUMS 2016 (6 states) → SILO-schema frames with binned income.
Outputs → outputs/01_preprocessed/{hh,pp}.parquet
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from vaelib import config, crosswalks, preprocessing

OUT = config.OUTPUTS_DIR / "01_preprocessed"
OUT.mkdir(parents=True, exist_ok=True)

coverage = crosswalks.load_coverage_fractions()
mstm = crosswalks.mstm_puma_set()
print(f"MSTM PUMAs: {len(mstm)} | partial-coverage PUMAs: {len(coverage)}", flush=True)

all_hh, all_pp = [], []
for fips in config.MSTM_STATE_FIPS:
    ab = config.STATE_FIPS_ABBREV[fips].lower()
    hz, pz = config.PUMS_DIR / f"csv_h{ab}.zip", config.PUMS_DIR / f"csv_p{ab}.zip"
    if not hz.exists():
        print(f"  skip {ab.upper()}: missing {hz.name}"); continue
    t = time.time()
    hh, pp = preprocessing.preprocess_state(fips, hz, pz, coverage, mstm)
    print(f"  {config.STATE_FIPS_ABBREV[fips]:<3}: {len(hh):>7,} HH, {len(pp):>7,} PP  [{time.time()-t:.1f}s]", flush=True)
    all_hh.append(hh); all_pp.append(pp)

hh = pd.concat(all_hh, ignore_index=True)
pp = pd.concat(all_pp, ignore_index=True)
hh.to_parquet(OUT / "hh.parquet", index=False)
pp.to_parquet(OUT / "pp.parquet", index=False)

# sanity checks
print(f"\nTOTAL: {len(hh):,} HH, {len(pp):,} PP")
print(f"  Σ WGTP_eff = {hh['WGTP_eff'].sum():,.0f} | Σ PWGTP_eff = {pp['PWGTP_eff'].sum():,.0f}")
print(f"  PUMAs in hh: {hh['puma_key'].nunique()}")
print(f"  HH income: median=${hh['income_hh'].median():,.0f}  max=${hh['income_hh'].max():,.0f}  bins={hh['income_bin'].nunique()}")
print(f"  PP non-earner share (income_bin==0): {(pp['income_bin']==0).mean()*100:.1f}%  (under-16 incl.)")
lic = pp.loc[pp['age']>=16,'driversLicense'].mean()
print(f"  adult licensed: {lic:.3f} | employed share: {(pp['occupation']==1).mean():.3f}")
print(f"  hhSize>7: {(hh['hhSize']>7).mean()*100:.2f}% (capped to 7 only for hhSizeVAE)")
print(f"saved → {OUT}")
