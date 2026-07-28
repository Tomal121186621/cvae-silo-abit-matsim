#!/usr/bin/env python3
"""TMAS 2023 hourly-profile validation at the I-695 corridor stations (+ key approach
freeways). Model hourly volumes recomputed from the frozen-base linkstats; observed
profiles from FHWA TMAS continuous count stations. Publication figure: no run/version
labels, station names in panel titles, profiles as share-of-daily so the temporal
test is independent of the documented resident-only volume scope.
"""
import re, gzip
import numpy as np, pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
LS = ROOT / "scenarios/02_i695_congestion_pricing/runs/loaded_base_v4/ITERS/it.15/15.linkstats.txt.gz"
TMAS = ROOT / "network_validation_2023/tmas"
OUT = ROOT / "trb_paper/figures/counts"

STATIONS = [  # station_id -> clean panel title
    ("0P0032", "I-695 at Ingleside Ave\n(west beltway)"),
    ("0P0077", "I-695 at Hollins Ferry Rd\n(southwest beltway)"),
    ("0P0078", "I-695 south of I-795\n(northwest beltway)"),
    ("0P0054", "I-695 at Cromwell Bridge Rd\n(northeast beltway)"),
    ("0P0074", "I-695 at Trappe Rd\n(east beltway)"),
    ("0P0071", "I-95 north of I-195\n(southwest approach)"),
    ("0P0052", "I-83 north of I-695\n(north approach)"),
    ("0P0053", "I-70 west of I-695\n(west approach)"),
]

plt.rcParams.update({"font.family": "serif", "font.size": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})

val = pd.read_csv(TMAS / "tmas_validation_2023.csv", dtype={"station_id": str})
prof = pd.read_csv(TMAS / "station_profiles.csv", dtype={"station_id": str}).set_index("station_id")

ls = pd.read_csv(LS, sep="\t", low_memory=False)
hrcols = [c for c in ls.columns
          if (m := re.fullmatch(r"HRS(\d+)-(\d+)avg", c)) and int(m[2]) - int(m[1]) == 1]
hrcols.sort(key=lambda c: int(re.match(r"HRS(\d+)-", c).group(1)))
assert len(hrcols) == 24, hrcols
ls["LINK"] = ls["LINK"].astype(str)
lk = ls.set_index("LINK")[hrcols]

fig, axes = plt.subplots(2, 4, figsize=(6.8, 3.9), sharex=True, sharey=True,
                         gridspec_kw={"hspace": 0.52, "top": 0.80})
for ax, (sid, title) in zip(axes.flat, STATIONS):
    row = val[val.station_id == sid].iloc[0]
    links = [l for l in str(row.link_ids).split(";") if l in lk.index]
    mod = lk.loc[links, hrcols].sum(axis=0).to_numpy() * 10.0
    obs = prof.loc[sid, [f"obs_h{h}" for h in range(24)]].to_numpy(float)
    obs_s, mod_s = obs / obs.sum(), mod / mod.sum()
    r = np.corrcoef(obs_s, mod_s)[0, 1]
    ax.plot(range(24), 100 * obs_s, color="#555555", lw=1.4, label="Observed (TMAS 2023)")
    ax.plot(range(24), 100 * mod_s, color="#2a78d6", lw=1.4, label="Simulated")
    ax.set_title(title, fontsize=7.0)
    ax.annotate(f"r = {r:.2f}", (0.03, 0.86), xycoords="axes fraction", fontsize=7.5)
    ax.set_xticks([0, 6, 12, 18, 24]); ax.grid(alpha=0.25, lw=0.4)
for ax in axes[1]: ax.set_xlabel("hour of day")
for ax in axes[:, 0]: ax.set_ylabel("share of daily (%)")
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 0.92))
fig.suptitle("Hourly traffic profiles at I-695 corridor count stations — simulated vs TMAS",
             fontsize=10, y=0.99)
fig.savefig(OUT / "fig_tmas_i695_stations.pdf"); fig.savefig(OUT / "fig_tmas_i695_stations.png")
print("saved fig_tmas_i695_stations; mean r =",
      round(np.mean([np.corrcoef(
          prof.loc[s, [f'obs_h{h}' for h in range(24)]].to_numpy(float) /
          prof.loc[s, [f'obs_h{h}' for h in range(24)]].to_numpy(float).sum(),
          lk.loc[[l for l in str(val[val.station_id == s].iloc[0].link_ids).split(';') if l in lk.index],
                 hrcols].sum(axis=0).to_numpy() /
          lk.loc[[l for l in str(val[val.station_id == s].iloc[0].link_ids).split(';') if l in lk.index],
                 hrcols].sum(axis=0).to_numpy().sum())[0, 1] for s, _ in STATIONS]), 3))
