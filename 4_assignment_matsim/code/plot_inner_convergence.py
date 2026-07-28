#!/usr/bin/env python3
"""INNER-loop (within-MATSim) convergence figure — the route + departure-time relaxation inside ONE
MATSim run (modes FIXED). Two panels, TRB/Times style:
  (1) avg EXECUTED / BEST / WORST plan score vs iteration -> rises and PLATEAUS (equilibrium); a vertical
      marker at the innovation-off iteration (80% of last iter) shows where new routes/times stop being
      generated and the selector relaxes onto the frozen choice set.
  (2) PHYSICAL system settling: total car person-hours (from ph_modestats) vs iteration -> falls as
      ReRoute finds faster paths, then plateaus. Confirms the network (not just the score) has settled.

Run per MATSim run (base + each toll outer-iter). Usage:
  plot_inner_convergence.py <run_dir> <label> [title]
Writes FINAL_FIGURES/convergence/inner_<label>.png/.pdf
"""
import sys, csv
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
FIG  = ROOT/"network_validation_2023/FINAL_FIGURES/convergence"
plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "font.size":10,"axes.linewidth":0.7,"savefig.dpi":600,"figure.dpi":120,"legend.frameon":False})

def _read_delim(p):
    with open(p) as f: first=f.readline()
    return ";" if first.count(";")>=first.count(",") else ","

def _find(cols, *keys):
    for c in cols:
        cl=c.lower()
        if all(k in cl for k in keys): return c
    return None

def main():
    run=Path(sys.argv[1]); label=sys.argv[2]; title=sys.argv[3] if len(sys.argv)>3 else label
    FIG.mkdir(parents=True, exist_ok=True)
    ss=pd.read_csv(run/"scorestats.csv", sep=_read_delim(run/"scorestats.csv"))
    ss.columns=[c.strip() for c in ss.columns]
    it=_find(ss.columns,"iteration") or ss.columns[0]
    c_exec=_find(ss.columns,"executed") or _find(ss.columns,"avg","exec")
    c_best=_find(ss.columns,"best"); c_worst=_find(ss.columns,"worst")
    c_avg =_find(ss.columns,"average") or _find(ss.columns,"avg","avg")

    fig,axs=plt.subplots(1,2,figsize=(10.5,4.1))
    ax=axs[0]
    x=ss[it].to_numpy()
    for col,lab,c,ls in [(c_best,"best","#1f77b4","-"),(c_exec,"executed","#d62728","-"),
                         (c_avg,"avg in memory","#2ca02c","--"),(c_worst,"worst","#7f7f7f",":")]:
        if col is not None: ax.plot(x, ss[col], ls, color=c, lw=1.5, label=lab)
    last=int(x.max()); ioff=int(round(0.8*last))
    ax.axvline(ioff, color="k", lw=0.8, ls=(0,(4,3)), alpha=0.7)
    ax.annotate("innovation off (80%)", xy=(ioff, ax.get_ylim()[0]),
                xytext=(ioff+0.5, ax.get_ylim()[0]+0.05*(ax.get_ylim()[1]-ax.get_ylim()[0])),
                fontsize=8, rotation=90, va="bottom")
    # plateau annotation: last-5-iter mean of executed
    if c_exec is not None:
        plat=ss[c_exec].tail(min(5,len(ss))).mean()
        ax.axhline(plat, color="#d62728", lw=0.6, alpha=0.4)
        ax.annotate(f"plateau ≈ {plat:.1f}", xy=(x[len(x)//4], plat), fontsize=8, color="#d62728", va="bottom")
    ax.set_xlabel("MATSim iteration"); ax.set_ylabel("plan score [utils]")
    ax.set_title("(a) Score relaxation (route + departure-time)"); ax.legend(loc="lower right", fontsize=8)

    # panel 2: physical settling — total car person-hours
    ax2=axs[1]
    php=run/"ph_modestats.csv"
    if php.exists():
        ph=pd.read_csv(php, sep=_read_delim(php)); ph.columns=[c.strip() for c in ph.columns]
        pit=_find(ph.columns,"iteration") or ph.columns[0]
        cc=_find(ph.columns,"car","travel")
        if cc is not None:
            ax2.plot(ph[pit], ph[cc]/1e3, "-", color="#ff7f0e", lw=1.6)
            ax2.set_ylabel("total car travel [1000 person-h]")
            v=ph[cc].tail(min(5,len(ph))).mean()/1e3
            ax2.axhline(v, color="#ff7f0e", lw=0.6, alpha=0.4)
            ax2.annotate(f"settled ≈ {v:.0f}k p-h", xy=(ph[pit].iloc[len(ph)//3], v), fontsize=8, va="bottom")
    ax2.axvline(ioff, color="k", lw=0.8, ls=(0,(4,3)), alpha=0.7)
    ax2.set_xlabel("MATSim iteration"); ax2.set_title("(b) Physical settling (network travel time)")
    fig.suptitle(f"Inner-loop (within-MATSim) convergence — {title}", fontsize=11)
    fig.tight_layout(rect=(0,0,1,0.96))
    for ext in ("png","pdf"): fig.savefig(FIG/f"inner_{label}.{ext}", bbox_inches="tight")
    print(f"wrote {FIG/('inner_'+label)}.png/.pdf  (last iter {last}, plateau score "
          f"{ss[c_exec].tail(5).mean():.1f})" if c_exec is not None else f"wrote inner_{label}")

if __name__=="__main__":
    main()
