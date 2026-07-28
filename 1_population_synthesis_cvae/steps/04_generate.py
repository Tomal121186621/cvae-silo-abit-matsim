#!/usr/bin/env python3
"""STEP 04 — generate the synthetic population from the trained CVAE (EMA weights).
Outputs → outputs/04_generated/{hh,pp}.parquet

Usage: python steps/04_generate.py [--tag full] [--n N] [--device cpu]
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np, pandas as pd, torch
from vaelib import config, crosswalks
from vaelib.model import CVAE, CVAEConfig
from vaelib.zones import ZoneSampler
from vaelib.generate import generate_population
from vaelib.consistency import count_structural_zeros

ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="full")
ap.add_argument("--n", type=int, default=0, help="0 = full weighted population")
ap.add_argument("--device", default="cpu")
args = ap.parse_args()

PRE = config.OUTPUTS_DIR / "01_preprocessed"
TGT = config.OUTPUTS_DIR / "02_targets"
CKPT = config.OUTPUTS_DIR / "03_training" / args.tag / "checkpoint_best.pt"
OUT = config.OUTPUTS_DIR / "04_generated"; OUT.mkdir(parents=True, exist_ok=True)

hh = pd.read_parquet(PRE / "hh.parquet"); pp = pd.read_parquet(PRE / "pp.parquet")
puma_to_idx = json.loads((TGT / "puma_to_idx.json").read_text())

state = torch.load(CKPT, map_location=args.device, weights_only=False)
model = CVAE(n_pumas=len(puma_to_idx), cfg=CVAEConfig(**state["model_cfg"]))
model.load_state_dict(state["ema_state"])     # EMA weights for inference
model.to(args.device)
print(f"loaded EMA checkpoint @ epoch {state['epoch']}", flush=True)

zone_df = crosswalks.build_zone_table()
zsamp = ZoneSampler(zone_df, rng=np.random.default_rng(0))

n_total = args.n if args.n > 0 else None
gen_hh, gen_pp = generate_population(model, hh, pp, puma_to_idx, zsamp,
                                     n_total=n_total, seed=0, device=args.device)
gen_hh.to_parquet(OUT / "hh.parquet", index=False)
gen_pp.to_parquet(OUT / "pp.parquet", index=False)

# sanity + structural-zero gate
sz = count_structural_zeros(gen_pp, hh=gen_hh)
print(f"generated: {len(gen_hh):,} HH / {len(gen_pp):,} PP  (persons/HH={len(gen_pp)/len(gen_hh):.2f})")
print(f"  HH income: median=${gen_hh['income_hh'].median():,.0f}  max=${gen_hh['income_hh'].max():,.0f}")
print(f"  >$300k share: {(gen_hh['income_hh']>300_000).mean()*100:.2f}%  "
      f">$1M: {(gen_hh['income_hh']>1_000_000).mean()*100:.3f}%")
print(f"  PP non-earner (income<=0): {(gen_pp['income']<=0).mean()*100:.1f}%")
sigma_ok = (gen_pp.groupby('hh_id')['income'].sum() ==
            gen_hh.set_index('hh_id')['income_hh']).mean()
print(f"  Σperson==HH income exact: {sigma_ok*100:.1f}% of households")
print(f"  STRUCTURAL ZEROS: {sz['total']}  detail={ {k:v for k,v in sz.items() if v>0} }")
print(f"saved → {OUT}")
