#!/usr/bin/env python3
"""I-695 corridor validation scatter, styled like the all-station validation figure:
log-log axes, 1:1 line, constant ±25% and ±50% bands as parallel colored lines.
Suspected ramp/partial count-matches are excluded from the plot and statistics."""
import numpy as np, pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
d = pd.read_csv(ROOT / "trb_paper/figures/counts/i695_station_validation.csv")
# suspected ramp/partial counts (ramp-scale obs snapped to mainline links) — excluded
SUSPECT = {"B1197", "T0006", "B1198", "B1093", "B1096", "P0074", "B1095"}
d = d[~d.LOCATION_ID.isin(SUSPECT)]
obs, sim = d.obs_AADT.to_numpy() / 1e3, d.m.to_numpy() / 1e3

r2 = np.corrcoef(obs, sim)[0, 1] ** 2
rd = (sim - obs) / obs
w50 = 100 * (abs((sim - obs) / obs) <= 0.50).mean()

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
fig, ax = plt.subplots(figsize=(4.4, 4.4))
lo, hi = 40, 280
xx = np.array([1.0, 400.0])
ax.plot(xx, xx, color="0.25", lw=1.1, zorder=2, label="1:1")
ax.plot(xx, 1.50 * xx, "k:", lw=0.9, zorder=2)
ax.plot(xx, 0.50 * xx, "k:", lw=0.9, zorder=2, label="±50% band")
ax.scatter(obs, sim, s=30, color="#0072B2", edgecolors="white", linewidth=0.6,
           alpha=0.9, zorder=3, label="I-695 count station")
ax.annotate(f"n = {len(d)} stations\n$R^2$ = {r2:.2f}\n"
            f"$\\Sigma$sim/$\\Sigma$obs = {sim.sum()/obs.sum():.2f}\n"
            f"within ±50%: {w50:.0f}%",
            (0.04, 0.97), xycoords="axes fraction", va="top", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.7", lw=0.6))
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
tks = [50, 100, 150, 200, 250]
ax.set_xticks(tks); ax.set_yticks(tks)
fmt = plt.FuncFormatter(lambda v, _: f"{v:g}")
ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
ax.minorticks_off()
ax.set_xlabel("Observed AADT 2023 (thousand veh/day)")
ax.set_ylabel("Simulated daily volume (thousand veh/day)")
ax.set_title("I-695 corridor: simulated vs observed daily volumes", fontsize=9.5)
ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.grid(alpha=0.25, lw=0.4, which="major")
out = ROOT / "trb_paper/figures/corridors"
fig.savefig(out / "corridor_i695_scatter.pdf"); fig.savefig(out / "corridor_i695_scatter.png")
print(f"saved corridor_i695_scatter  R2={r2:.3f}  within ±50%: {w50:.0f}%")
