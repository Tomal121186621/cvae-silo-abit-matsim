#!/usr/bin/env python3
"""TRB paper figures 1/2: mode-choice calibration story (no events file needed).

F1  mode share: frozen base vs ABIT target (grouped bars, log-free two-panel)
F2  the innovation-off cliff: pass5 (innovoff=0.8) vs pass7 (innovoff=1.0) car-share traces
F3  calibration history: final shares by pass vs targets

Passes 1-5 final shares and the pass-5 per-iteration trace are transcribed from the
run logs (directories were cleaned for disk); pass7/pass8 are read from modestats.csv.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
CAL = ROOT / "scenarios/01_base_no_pricing/output_calib_fs"
OUT = ROOT / "trb_paper/figures"; OUT.mkdir(parents=True, exist_ok=True)

# validated categorical palette (dataviz slots 1-6, light mode)
C = {"car": "#2a78d6", "ride": "#1baf7a", "pt": "#eda100", "walk": "#008300", "bike": "#4a3aa7", "target": "#6b6a63"}
MODES = ["car", "ride", "pt", "walk", "bike"]
TARGET = {"car": 77.6, "ride": 16.3, "pt": 1.8, "walk": 3.66, "bike": 0.68}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
                     "figure.dpi": 300, "savefig.bbox": "tight", "font.family": "Helvetica"})

def read_modestats(p):
    rows = list(csv.DictReader(open(p), delimiter=";"))
    return {m: [100 * float(r[m]) for r in rows] for m in MODES}

p7 = read_modestats(CAL / "pass7/modestats.csv")
p8 = read_modestats(CAL / "pass8/modestats.csv")
FROZEN = {m: p8[m][-1] for m in MODES}

# transcribed from run logs (dirs cleaned): pass-5 full car trace (innovoff=0.8 cliff at it.13)
P5_CAR = [82.40, 72.82, 72.38, 71.99, 72.02, 72.00, 71.99, 72.09, 72.07, 72.17, 72.14, 72.09, 72.13, 81.17, 81.19, 81.22]
# final-iteration shares per pass (1-5 from logs; 6-8 from files/above)
HIST = {  # pass: (car, ride, pt, walk, bike)
    1: (81.10, 11.75, 2.85, 3.74, 0.56), 2: (81.58, 13.39, 1.67, 2.84, 0.51),
    3: (82.40, 13.00, 1.61, 2.60, 0.40), 4: (82.23, 13.83, 1.42, 2.18, 0.34),
    5: (81.22, 13.09, 2.42, 2.64, 0.63), 6: (72.99, 16.91, 3.87, 4.79, 1.44),
    7: (round(p7["car"][-1], 2), round(p7["ride"][-1], 2), round(p7["pt"][-1], 2), round(p7["walk"][-1], 2), round(p7["bike"][-1], 2)),
    8: tuple(round(FROZEN[m], 2) for m in MODES),
}

# ---- F1: frozen base vs target -------------------------------------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.5, 2.6), gridspec_kw={"width_ratios": [2, 3]})
for ax, modes in ((a1, ["car", "ride"]), (a2, ["pt", "walk", "bike"])):
    x = range(len(modes)); w = 0.38
    tb = ax.bar([i - w/2 for i in x], [TARGET[m] for m in modes], w, color=C["target"], label="ABIT target")
    sb = ax.bar([i + w/2 for i in x], [FROZEN[m] for m in modes], w,
                color=[C[m] for m in modes], label="MATSim base")
    for b, v in zip(list(tb) + list(sb), [TARGET[m] for m in modes] + [FROZEN[m] for m in modes]):
        ax.annotate(f"{v:.2f}" if v < 10 else f"{v:.1f}", (b.get_x() + b.get_width()/2, v),
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x)); ax.set_xticklabels([m.upper() if m == "pt" else m for m in modes])
    ax.set_ylim(0, max(TARGET[m] for m in modes) * 1.25); ax.grid(axis="x", visible=False)
a1.set_ylabel("mode share (%)")
a1.legend(frameon=False, fontsize=8, loc="upper right")
fig.suptitle("Converged mode shares vs ABIT demand-model targets", fontsize=10, y=1.03)
fig.savefig(OUT / "F1_modeshare_vs_target.pdf"); fig.savefig(OUT / "F1_modeshare_vs_target.png")

# ---- F2: the innovation-off cliff ----------------------------------------------
fig, ax = plt.subplots(figsize=(4.5, 2.8))
ax.plot(range(len(P5_CAR)), P5_CAR, color=C["ride"], lw=2, label="innovation off at 80% (MATSim default)")
ax.plot(range(len(p7["car"])), p7["car"], color=C["car"], lw=2, label="innovation always on (this study)")
ax.axhline(TARGET["car"], color=C["target"], lw=1, ls="--")
ax.annotate("ABIT target 77.6%", (15, TARGET["car"] + 0.3), fontsize=8, color=C["target"], ha="right")
ax.axvline(12.5, color=C["ride"], lw=0.8, ls=":", alpha=0.7)
ax.annotate("mode innovation\ndisabled", (12.2, 74.8), fontsize=8, ha="right", color=C["ride"])
ax.set_xlabel("iteration"); ax.set_ylabel("car share (%)"); ax.set_ylim(70, 84)
ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("Selection collapse when mode innovation is disabled", fontsize=10)
fig.savefig(OUT / "F2_innovation_cliff.pdf"); fig.savefig(OUT / "F2_innovation_cliff.png")

# ---- F3: calibration history ----------------------------------------------------
fig, axes = plt.subplots(1, 5, figsize=(6.5, 2.2), sharex=True)
passes = sorted(HIST)
for ax, m, i in zip(axes, MODES, range(5)):
    ax.plot(passes, [HIST[p][i] for p in passes], "o-", color=C[m], lw=1.5, ms=3.5)
    ax.axhline(TARGET[m], color=C["target"], lw=1, ls="--")
    ax.set_title(m.upper() if m == "pt" else m, fontsize=9)
    ax.axvspan(5.5, 8.4, color=C[m], alpha=0.06)
    ax.grid(axis="x", visible=False)
axes[0].set_ylabel("share (%)")
for ax in axes: ax.set_xlabel("pass"); ax.set_xticks(passes)
fig.suptitle("Calibration history (shaded: after measurement fix, passes 6–8; dashed: ABIT target)",
             fontsize=9.5, y=1.06)
fig.savefig(OUT / "F3_calibration_history.pdf"); fig.savefig(OUT / "F3_calibration_history.png")
print("wrote", len(list(OUT.glob("F*.p*"))), "files to", OUT)
