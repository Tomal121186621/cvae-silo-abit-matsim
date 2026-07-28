#!/usr/bin/env python3
"""OUTER-loop (ABIT mode-choice <-> MATSim congested/tolled-skim) convergence figure — the NEW one.
Reads outerloop_convergence.csv (written by run_feedback.py each outer iteration) and plots the
iteration-over-iteration deltas, which should DECAY toward ~0 as the mode split and the skims stop
changing. Marks the convergence threshold and the first iteration meeting it (~3-5).

Metrics per outer iter n (vs n-1): |Δ car share| (pp), OD car-skim RMSE (min), monitoring-link volume
%RMSE, and the skim relative gap. This is the figure that demonstrates the mode-choice/assignment
feedback converged (distinct from the inner-loop within-MATSim route/departure-time relaxation).

Usage: plot_outer_convergence.py <outerloop_convergence.csv> <label> [title]
Writes FINAL_FIGURES/convergence/outer_<label>.png/.pdf
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
FIG  = ROOT/"network_validation_2023/FINAL_FIGURES/convergence"
plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "font.size":10,"axes.linewidth":0.7,"savefig.dpi":600,"figure.dpi":120,"legend.frameon":False})
THRESH = {"dcar_share_pp":0.5, "skim_rmse_min":0.5, "linkvol_pct_rmse":5.0, "skim_relgap":0.03}

def main():
    csv=Path(sys.argv[1]); label=sys.argv[2]; title=sys.argv[3] if len(sys.argv)>3 else label
    FIG.mkdir(parents=True, exist_ok=True)
    d=pd.read_csv(csv); d=d.dropna(subset=["outer_iter"])
    x=d.outer_iter.to_numpy()
    series=[("dcar_share_pp","|Δ car share|","pp","#d62728",lambda v:np.abs(v)),
            ("skim_rmse_min","OD skim RMSE","min","#1f77b4",lambda v:v),
            ("linkvol_pct_rmse","link volume %RMSE","%","#2ca02c",lambda v:v),
            ("skim_relgap","skim relative gap","","#7f7f7f",lambda v:v)]
    fig,ax=plt.subplots(figsize=(7.4,4.6))
    conv_iter=None
    for col,lab,unit,c,fn in series:
        if col not in d.columns: continue
        y=fn(d[col].to_numpy(dtype=float)); m=np.isfinite(y)
        ax.plot(x[m], np.maximum(y[m],1e-4), "-o", color=c, lw=1.5, ms=4, label=f"{lab} [{unit}]" if unit else lab)
        ax.axhline(THRESH.get(col,np.nan), color=c, lw=0.6, ls=":", alpha=0.5)
    # first outer iter where ALL available metrics are under threshold
    for _,r in d.iterrows():
        ok=all((not np.isfinite(r.get(k,np.nan))) or (abs(r[k]) if k=="dcar_share_pp" else r[k])<=t
               for k,t in THRESH.items())
        if bool(ok) and r.outer_iter>=1: conv_iter=int(r.outer_iter); break
    ax.set_yscale("log"); ax.set_xlabel("outer iteration (ABIT re-choice on congested+tolled skims)")
    ax.set_ylabel("iteration-over-iteration change (log)")
    if conv_iter is not None:
        ax.axvline(conv_iter, color="k", lw=1.0, ls="--", alpha=0.7)
        ax.annotate(f"converged @ outer {conv_iter}", xy=(conv_iter, ax.get_ylim()[1]*0.5),
                    fontsize=9, ha="right", rotation=90, va="top")
    ax.set_xticks(x.astype(int)); ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Outer-loop (mode split ↔ tolled skims) convergence — {title}", fontsize=11)
    fig.tight_layout()
    for ext in ("png","pdf"): fig.savefig(FIG/f"outer_{label}.{ext}", bbox_inches="tight")
    print(f"wrote {FIG/('outer_'+label)}.png/.pdf ; converged at outer iter {conv_iter}")

if __name__=="__main__":
    main()
