#!/usr/bin/env python3
"""STEP 05 — workplace allocation (Path A): assign employed persons to job zones.
Outputs → outputs/05_workplace/{jj.parquet, workplace.parquet}
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np, pandas as pd
from vaelib import config
from vaelib.workplace import (SkimReader, CommuteTimeDistribution,
                              load_employment_forecast, WorkplaceAllocator)

GEN = config.OUTPUTS_DIR / "04_generated"
OUT = config.OUTPUTS_DIR / "05_workplace"; OUT.mkdir(parents=True, exist_ok=True)

gen_hh = pd.read_parquet(GEN / "hh.parquet")
gen_pp = pd.read_parquet(GEN / "pp.parquet")

emp = gen_pp.loc[gen_pp["occupation"] == 1, ["pp_id", "hh_id"]].merge(
    gen_hh[["hh_id", "zone_id"]], on="hh_id", how="left")
print(f"employed persons: {len(emp):,}", flush=True)

skim = SkimReader(); tlfd = CommuteTimeDistribution()
forecast = load_employment_forecast()
print(f"total job vacancies (forecast): {forecast['jobs'].sum():,}", flush=True)
alloc = WorkplaceAllocator(skim, tlfd, forecast, rng=np.random.default_rng(0))
workplace, jj = alloc.assign(emp[["pp_id", "zone_id"]], starting_job_id=1)

jj.to_parquet(OUT / "jj.parquet", index=False)
workplace.rename_axis("pp_id").reset_index().to_parquet(OUT / "workplace.parquet", index=False)
print(f"  jobs assigned: {len(jj):,} | unreachable(-1): {int((workplace==-1).sum()):,} | "
      f"external(-2): {int((workplace==-2).sum()):,}")
print(f"saved → {OUT}")
