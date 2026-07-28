#!/usr/bin/env python3
"""STEP 02 — build per-PUMA marginal targets + PUMA index from preprocessed frames.
(The within-(PUMA,bin) income sampler is rebuilt at generation from the same frames.)
Outputs → outputs/02_targets/{puma_targets.json, puma_to_idx.json}
"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from vaelib import config, crosswalks, targets as T

PRE = config.OUTPUTS_DIR / "01_preprocessed"
OUT = config.OUTPUTS_DIR / "02_targets"; OUT.mkdir(parents=True, exist_ok=True)

hh = pd.read_parquet(PRE / "hh.parquet")
pp = pd.read_parquet(PRE / "pp.parquet")

# PUMA index must cover every PUMA in the data AND the zone system.
zone_df = crosswalks.build_zone_table()
all_pumas = set(hh["puma_key"].unique()) | set(zone_df["puma_key"].unique())
puma_to_idx = crosswalks.build_puma_to_idx(all_pumas)
(OUT / "puma_to_idx.json").write_text(json.dumps(puma_to_idx, indent=1, sort_keys=True))

puma_targets = T.build_puma_targets(hh, pp, mstm_pumas=puma_to_idx.keys())
T.save_targets(puma_targets, OUT / "puma_targets.json")

# sanity
nonempty = sum(1 for d in puma_targets.values() if d)
print(f"PUMAs indexed: {len(puma_to_idx)} | with targets: {nonempty}")
ex = next(pk for pk, d in puma_targets.items() if d)
print(f"example PUMA {ex}: vars = {sorted(puma_targets[ex].keys())}")
print(f"  dwellingType sums to {sum(puma_targets[ex]['dwellingType']):.3f}, "
      f"HH income_bin sums to {sum(puma_targets[ex]['income_bin']):.3f}, "
      f"pp_income_bin sums to {sum(puma_targets[ex]['pp_income_bin']):.3f}")
print(f"saved → {OUT}")
