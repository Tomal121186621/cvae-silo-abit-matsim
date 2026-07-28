#!/usr/bin/env python3
"""Corridor validation summary: one lollipop chart of Sigma sim / Sigma obs per corridor
(replaces the per-corridor side-by-side bar charts)."""
import pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
sm = pd.read_csv(ROOT / "trb_paper/figures/corridors/corridor_summary.csv").sort_values("vol_ratio")

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
fig, ax = plt.subplots(figsize=(5.6, 3.6))
y = range(len(sm))
ax.axvspan(0.90, 1.10, color="#c8e6c9", alpha=0.55, zorder=0)
ax.axvspan(0.80, 0.90, color="#fff3c4", alpha=0.5, zorder=0)
ax.axvspan(1.10, 1.20, color="#fff3c4", alpha=0.5, zorder=0)
ax.axvline(1.0, color="0.3", lw=0.9)
cols = ["#D55E00" if (r < 0.8 or r > 1.2) else "#0072B2" for r in sm.vol_ratio]
ax.hlines(y, 1.0, sm.vol_ratio, color=cols, lw=1.6, zorder=3)
ax.scatter(sm.vol_ratio, y, s=42, color=cols, zorder=4)
for yi, r in zip(y, sm.itertuples()):
    ax.annotate(f"{r.vol_ratio:.2f}", (r.vol_ratio, yi), xytext=(8 if r.vol_ratio >= 1 else -8, 0),
                textcoords="offset points", va="center",
                ha="left" if r.vol_ratio >= 1 else "right", fontsize=7.5)
ax.set_yticks(list(y))
ax.set_yticklabels([c.replace(" (tolled)", "").replace(" (I-70/I-695 parallel)", "")
                    .replace(" (I-95 parallel)", "") for c in sm.corridor], fontsize=8)
ax.set_xlabel("simulated / observed daily volume (corridor total)")
ax.set_xlim(0.55, 1.35)
ax.legend(handles=[Patch(fc="#c8e6c9", label="within ±10%"), Patch(fc="#fff3c4", label="±20%")],
          frameon=False, fontsize=7.5, loc="lower right")
ax.set_title("Corridor volume validation", fontsize=10)
fig.savefig(ROOT / "trb_paper/figures/corridors/corridor_summary_ratios.pdf")
fig.savefig(ROOT / "trb_paper/figures/corridors/corridor_summary_ratios.png")
print("saved corridor_summary_ratios")
