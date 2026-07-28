#!/usr/bin/env python3
"""STEP 06 — dwelling donor-fill + SILO CSV export (hh/pp/dd/jj).
Outputs → outputs/06_silo_input/{hh,pp,dd,jj}_2016.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from vaelib import config
from vaelib.dwelling import fill_dwelling_attrs
from vaelib.silo_export import to_silo_schema

GEN = config.OUTPUTS_DIR / "04_generated"
WP = config.OUTPUTS_DIR / "05_workplace"
PRE = config.OUTPUTS_DIR / "01_preprocessed"
OUT = config.OUTPUTS_DIR / "06_silo_input"; OUT.mkdir(parents=True, exist_ok=True)

gen_hh = pd.read_parquet(GEN / "hh.parquet")
gen_pp = pd.read_parquet(GEN / "pp.parquet")
pums_hh = pd.read_parquet(PRE / "hh.parquet")

gen_hh = fill_dwelling_attrs(gen_hh, pums_hh, seed=0)

jj_df = workplace = None
if (WP / "jj.parquet").exists():
    jj_df = pd.read_parquet(WP / "jj.parquet")
    wp = pd.read_parquet(WP / "workplace.parquet")
    workplace = wp.set_index("pp_id")["workplace"]

paths = to_silo_schema(gen_hh, gen_pp, OUT, base_year=config.BASE_YEAR,
                       jj_df=jj_df, workplace_by_pp=workplace)
for k, p in paths.items():
    print(f"  {k}: {p.name}  ({sum(1 for _ in open(p))-1:,} rows)")
print(f"saved → {OUT}")
