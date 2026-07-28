#!/usr/bin/env python3
"""Light TRB/TRR re-render of the by-facility figA/figB/figC (scatter / GEH<5 share /
rel-bias) for the v7 base run, WITHOUT the heavy validate_base_hybrid orchestrator
(no events, no speed/transit subprocesses). Reuses counts()+fig_counts() only,
reading the base_calibrated it.64 linkstats + the cleaned AADT table.

Outputs -> network_validation_2023/v7_base/TRB_figures/ (originals untouched)."""
import os, sys
from pathlib import Path

CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")  # shared trb_style
# point the shared netval config at the v7 base run BEFORE importing it
os.environ["NETVAL_OUTDIR"] = "scenarios/02_i695_congestion_pricing/output_base/base_calibrated"
os.environ["NETVAL_ITER"]   = "64"
os.environ["NETVAL_SUB"]    = "v7_base/TRB_figures"

import trb_style; trb_style.apply()
import validate_base_hybrid as V
trb_style.apply()   # re-assert shared style over V's module-level serif rcParams

# palette-align the facility colours used inside fig_counts
V.FAC_COL = {"Interstate/Freeway": trb_style.PALETTE[1], "Principal Arterial": trb_style.PALETTE[3],
             "Minor Arterial": trb_style.PALETTE[2], "Collector/Local": trb_style.PALETTE[0]}

# inject TRR captions by wrapping V.save
_CAP = {
    "figA_scatter_by_facility": "Figure 1. Simulated vs. observed AADT 2023 by facility class "
        "(log-log; per-class OLS fits dashed; I-695 mainline-link stations circled).",
    "figB_geh_by_facility": "Figure 2. Share of count stations meeting GEH < 5 by facility class.",
    "figC_relbias_by_facility": "Figure 3. Median relative volume bias by facility class "
        "(resident-only demand scope).",
}
import matplotlib.pyplot as plt
_orig_save = V.save
def _save(fig, name):
    if name in _CAP:
        trb_style.caption(fig, _CAP[name])
    _orig_save(fig, name)
V.save = _save

ls = V.load_linkstats()
df, tab_raw, tab_clean, drop = V.counts(ls)
i695_ids = set(x for x in (V.ROOT/"scenarios/toll_research/i695_link_ids.txt").read_text().splitlines()
               if x and not x.startswith("#"))
V.fig_counts(df, i695_ids)
print("wrote figABC ->", V.OUTDIR)
