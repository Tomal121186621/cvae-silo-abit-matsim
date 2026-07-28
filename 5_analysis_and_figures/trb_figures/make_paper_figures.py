#!/usr/bin/env python3
"""Assemble the submission-ready TRB figure set in trb_paper/paper_figures/:
  fig1_study_area           (copy of F5 gateway + tolled crossings map)
  fig2_modechoice_equilibrium (copy of F2 innovation cliff)
  fig3_validation_composite (NEW: 4-panel — all-station scatter, corridor lollipop,
                             screenline deviation, TMAS hourly profiles)
  fig4_mode_shares          (copy of figM1)
Uniform serif style, one headline metric per panel, no GEH/no side-by-side bars.
"""
import re, shutil
import numpy as np, pandas as pd
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
F = ROOT / "trb_paper/figures"
OUT = ROOT / "trb_paper/paper_figures"; OUT.mkdir(exist_ok=True)
LS4 = ROOT / "scenarios/02_i695_congestion_pricing/runs/loaded_base_v4/ITERS/it.15/15.linkstats.txt.gz"
QA = ROOT / "network_validation_2023/transitfix/aadt/aadt_validation_2023_qa_v2.csv"

for src, dst in [("F5_gateway_seed_map", "fig1_study_area"),
                 ("F2_innovation_cliff", "fig2_modechoice_equilibrium"),
                 ("modeshare/figM1_mode_shares", "fig4_mode_shares")]:
    for ext in (".pdf", ".png"):
        shutil.copy(F / (src + ext), OUT / (dst + ext))
print("copied fig1, fig2, fig4")

plt.rcParams.update({"font.family": "serif", "font.size": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
fig = plt.figure(figsize=(7.0, 6.6))
gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.34)

# (a) all-stations scatter, log-log thousands
ax = fig.add_subplot(gs[0, 0])
ls = pd.read_csv(LS4, sep="\t", low_memory=False, dtype={"LINK": str})
vol = dict(zip(ls.LINK, pd.to_numeric(ls["HRS0-24avg"], errors="coerce") * 10))
qa = pd.read_csv(QA)
qa = qa[qa.link_ids.notna() & (qa.obs_AADT > 0) & (qa.facility != "Ramp")].copy()
qa["m"] = qa.link_ids.apply(lambda s: sum(vol.get(l.strip(), 0) for l in str(s).split(";")))
o, m = qa.obs_AADT / 1e3, (qa.m / 1e3).clip(lower=0.2)
COL = {"Interstate/Freeway": "#D55E00", "Principal Arterial": "#E69F00",
       "Minor Arterial": "#009E73", "Collector/Local": "#0072B2"}
for fac, g in qa.groupby("facility"):
    ax.scatter(g.obs_AADT/1e3, (g.m/1e3).clip(lower=0.2), s=5, c=COL[fac], alpha=0.4, lw=0, label=fac)
lim = [0.2, 300]; xx = np.array(lim)
ax.plot(xx, xx, "k-", lw=0.8); ax.plot(xx, 1.5*xx, "k:", lw=0.8); ax.plot(xx, 0.5*xx, "k:", lw=0.8)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
fmt = plt.FuncFormatter(lambda v, _: f"{v:g}")
ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
r2 = np.corrcoef(qa.m, qa.obs_AADT)[0, 1] ** 2
ax.text(0.03, 0.97, f"n = {len(qa):,}\n$\\Sigma$sim/$\\Sigma$obs = {qa.m.sum()/qa.obs_AADT.sum():.2f}\ncorr$^2$ = {r2:.2f}",
        transform=ax.transAxes, va="top", fontsize=7.5)
ax.legend(frameon=False, fontsize=5.8, loc="lower right", handletextpad=0.1)
ax.set_xlabel("Observed AADT (thousand veh/day)", fontsize=8)
ax.set_ylabel("Simulated (thousand veh/day)", fontsize=8)
ax.set_title("(a) Daily volumes, all count stations", fontsize=9)

# (b) corridor lollipop
ax = fig.add_subplot(gs[0, 1])
sm = pd.read_csv(F / "corridors/corridor_summary.csv").sort_values("vol_ratio")
y = range(len(sm))
ax.axvline(1.0, color="0.3", lw=0.8)
cols = ["#D55E00" if (r < 0.8 or r > 1.2) else "#0072B2" for r in sm.vol_ratio]
ax.hlines(y, 1.0, sm.vol_ratio, color=cols, lw=1.4, zorder=3)
ax.scatter(sm.vol_ratio, y, s=26, color=cols, zorder=4)
ax.set_yticks(list(y))
ax.set_yticklabels([c.replace(" (tolled)", "").replace(" Baltimore Beltway", "")
                    .replace(" (I-70/I-695 parallel)", "").replace(" (I-95 parallel)", "")
                    .replace(" Balt-Wash Pkwy", "").replace(" Reisterstown Rd", "").replace(" Ritchie Hwy", "")
                    .replace(" Harbor Tunnel", "") for c in sm.corridor], fontsize=7.5)
ax.set_xlim(0.55, 1.35); ax.set_xlabel("simulated / observed (corridor)", fontsize=8)
ax.set_title("(b) Corridor totals", fontsize=9)

# (c) screenline deviation
ax = fig.add_subplot(gs[1, 0])
sl = pd.read_csv(F / "screenlines/screenline_summary.csv")
x = np.arange(len(sl))
ax.axhline(0, color="0.3", lw=0.8)
cols = ["#D55E00" if abs(r.diff_pct) > 20 else "#0072B2" for r in sl.itertuples()]
ax.bar(x, sl.diff_pct, 0.55, color=cols, zorder=3)
for xi, r in zip(x, sl.itertuples()):
    ax.text(xi, r.diff_pct + (1.5 if r.diff_pct >= 0 else -1.5), f"{r.diff_pct:+.0f}%",
            ha="center", va="bottom" if r.diff_pct >= 0 else "top", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(["Harbor", "North", "West", "South", "East"], fontsize=8)
ax.set_ylabel("simulated vs observed (%)", fontsize=8)
ax.set_ylim(-50, 28)
ax.set_title("(c) Screenlines", fontsize=9)

# (d) TMAS hourly profiles, two representative stations
ax = fig.add_subplot(gs[1, 1])
val = pd.read_csv(ROOT / "network_validation_2023/tmas/tmas_validation_2023.csv", dtype={"station_id": str})
prof = pd.read_csv(ROOT / "network_validation_2023/tmas/station_profiles.csv", dtype={"station_id": str}).set_index("station_id")
hr = [c for c in ls.columns if (mm := re.fullmatch(r"HRS(\d+)-(\d+)avg", c)) and int(mm[2]) - int(mm[1]) == 1]
hr.sort(key=lambda c: int(re.match(r"HRS(\d+)-", c).group(1)))
lk = ls.set_index("LINK")[hr]
for sid, name, colr in [("0P0032", "I-695 west (Ingleside Ave)", "#0072B2"),
                        ("0P0077", "I-695 southwest (Hollins Ferry Rd)", "#D55E00")]:
    row = val[val.station_id == sid].iloc[0]
    links = [l for l in str(row.link_ids).split(";") if l in lk.index]
    mod = lk.loc[links, hr].sum(axis=0).to_numpy() * 10
    obs = prof.loc[sid, [f"obs_h{h}" for h in range(24)]].to_numpy(float)
    ax.plot(range(24), 100 * obs / obs.sum(), color=colr, lw=1.3, ls="--", alpha=0.75)
    ax.plot(range(24), 100 * mod / mod.sum(), color=colr, lw=1.5,
            label=f"{name} (r={np.corrcoef(obs/obs.sum(), mod/mod.sum())[0,1]:.2f})")
ax.plot([], [], color="0.4", ls="--", lw=1.2, label="observed (TMAS)")
ax.set_xticks([0, 6, 12, 18, 24]); ax.set_xlabel("hour of day", fontsize=8)
ax.set_ylabel("share of daily (%)", fontsize=8)
ax.set_ylim(0, 10.8)
ax.legend(frameon=False, fontsize=6.4, loc="upper right")
ax.set_title("(d) I-695 hourly profiles vs TMAS", fontsize=9)

fig.savefig(OUT / "fig3_validation_composite.pdf"); fig.savefig(OUT / "fig3_validation_composite.png")
print("built fig3_validation_composite")
