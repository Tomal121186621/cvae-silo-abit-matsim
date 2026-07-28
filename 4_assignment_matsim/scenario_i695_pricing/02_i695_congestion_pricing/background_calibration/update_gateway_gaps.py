#!/usr/bin/env python3
"""Refresh gateways_2023.csv cur_vol/external against the FROZEN resident base
(pass8 it.10 linkstats) so the background seeds close the cordon gap relative to
the demand actually used in the pricing study (the old values were from v17).
Writes a .bak of the previous csv and a before/after report."""
import ast
import pandas as pd
from pathlib import Path

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GW = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
LS = ROOT / "scenarios/01_base_no_pricing/output_calib_fs/pass8/ITERS/it.10/10.linkstats.txt.gz"

ls = pd.read_csv(LS, sep="\t", low_memory=False, dtype={"LINK": str})
vol = dict(zip(ls.LINK, pd.to_numeric(ls["HRS0-24avg"], errors="coerce") * 10.0))

g = pd.read_csv(GW)
g.to_csv(str(GW) + ".bak_pre_pass8", index=False)
old = g[["road", "cur_vol", "external"]].copy()
g["cur_vol"] = g.lids.apply(lambda s: sum(vol.get(str(l), 0.0) for l in ast.literal_eval(s)))
g["external"] = (g.cordon_aadt - g.cur_vol).clip(lower=0.0)
g.to_csv(GW, index=False)

rpt = pd.DataFrame({"road": g.road, "cordon_aadt": g.cordon_aadt,
                    "cur_vol_old": old.cur_vol, "cur_vol_new": g.cur_vol.round(0),
                    "external_old": old.external, "external_new": g.external.round(0)})
print(rpt.to_string(index=False))
print(f"\ntotal external gap: old {old.external.sum():,.0f} -> new {g.external.sum():,.0f} veh/day")
