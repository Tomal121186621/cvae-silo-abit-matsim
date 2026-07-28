#!/usr/bin/env python3
"""TRB-quality figures for the 2023 network validation (AADT daily + TMAS hourly)."""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import sys; sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()
from netval2023_common import OUTDIR, geh, GROUP_ORDER

FIG=OUTDIR/"TRB_figures"; FIG.mkdir(parents=True,exist_ok=True)   # TRB/TRR-styled; figures/ untouched
# facility colours == paper-wide fixed map (same class -> same colour in every figure)
COL={**trb_style.FACILITY_COLORS, "Ramp":trb_style.PALETTE[4]}

def geh5_band(o):
    """model bounds m_lo,m_hi such that GEH(m,o)=5, for the shaded acceptance band."""
    a=2.0; b=-(4*o+25); c=2*o**2-25*o
    disc=np.sqrt(np.maximum(b**2-4*a*c,0))
    return (-b-disc)/(2*a), (-b+disc)/(2*a)

def fig_scatter(d):
    d=d[d.model_daily>0].copy()
    fig,ax=plt.subplots(figsize=(5.2,5.0))
    lo,hi=300,4e5
    xs=np.logspace(np.log10(lo),np.log10(hi),200)
    mlo,mhi=geh5_band(xs)
    ax.fill_between(xs,np.maximum(mlo,1),mhi,color="#BBBBBB",alpha=0.35,zorder=1,label="GEH < 5 band")
    ax.plot([lo,hi],[lo,hi],"--",color=trb_style.NEUTRAL,lw=0.9,zorder=2,label="1:1 line")
    for grp in GROUP_ORDER:
        s=d[d.facility==grp]
        if len(s): ax.scatter(s.obs_AADT,s.model_daily,s=9,c=COL[grp],alpha=0.55,
                              edgecolors="none",label=f"{grp} (n={len(s)})",zorder=3)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lo,hi); ax.set_ylim(lo,hi)
    ax.set_xlabel("Observed AADT 2023 (veh/day)")
    ax.set_ylabel(r"MATSim daily volume $\times$10 (veh/day)")
    ax.legend(loc="upper left",frameon=False)
    ax.grid(True,which="both",ls=":",lw=0.3,alpha=0.5)
    trb_style.save(fig, FIG/"a_scatter_matsim_vs_aadt",
        "Figure 1. Simulated MATSim base daily volume (×10) vs. observed MDOT SHA AADT 2023, by facility class.")
    print("wrote a_scatter_matsim_vs_aadt.png/.pdf")

def fig_geh_dist(d):
    d=d[d.model_daily>0].copy()
    g=geh(d.model_daily.values,d.obs_AADT.values)
    fig,ax=plt.subplots(figsize=(5.2,3.6))
    bins=np.arange(0,60,2.5)
    ax.hist(np.clip(g,0,59),bins=bins,color=trb_style.PALETTE[0],alpha=0.85,edgecolor="white",lw=0.4)
    ax.axvline(5,color=trb_style.PALETTE[2],lw=1.2,ls="--",label=f"GEH=5  ({100*np.mean(g<5):.0f}% below)")
    ax.axvline(10,color=trb_style.PALETTE[3],lw=1.2,ls="--",label=f"GEH=10 ({100*np.mean(g<10):.0f}% below)")
    ax.set_xlabel("GEH statistic (daily)"); ax.set_ylabel("Number of count stations")
    ax.legend(frameon=False); ax.grid(True,axis="y",ls=":",lw=0.3,alpha=0.5)
    trb_style.save(fig, FIG/"b_geh_distribution",
        f"Figure 2. Distribution of the daily GEH statistic across {len(d):,} AADT count stations.")
    print("wrote b_geh_distribution.png/.pdf")

def fig_ratio_box(d):
    d=d[d.model_daily>0].copy()
    d["ratio"]=d.model_daily/d.obs_AADT
    groups=[g for g in GROUP_ORDER if (d.facility==g).any()]
    data=[d[d.facility==g].ratio.clip(0,3).values for g in groups]
    fig,ax=plt.subplots(figsize=(5.4,3.8))
    bp=ax.boxplot(data,vert=True,patch_artist=True,widths=0.6,showfliers=False,
                  medianprops=dict(color="black",lw=1.2))
    for patch,g in zip(bp["boxes"],groups): patch.set_facecolor(COL[g]); patch.set_alpha(0.6)
    ax.axhline(1.0,color=trb_style.NEUTRAL,ls="--",lw=0.9,label="perfect (ratio=1)")
    ax.set_xticklabels([g.replace(" ","\n") for g in groups])
    ax.set_ylabel("Volume ratio  (MATSim$\\times$10 / observed)")
    ax.set_ylim(0,2.6)
    for i,g in enumerate(groups):
        med=np.median(d[d.facility==g].ratio); ax.text(i+1,2.42,f"med\n{med:.2f}",ha="center",va="top",fontsize=8)
    ax.legend(frameon=False,loc="upper right"); ax.grid(True,axis="y",ls=":",lw=0.3,alpha=0.5)
    trb_style.save(fig, FIG/"c_ratio_by_facility",
        "Figure 3. Assignment bias: simulated-to-observed volume ratio by facility class (boxplots, outliers hidden).")
    print("wrote c_ratio_by_facility.png/.pdf")

def fig_hourly(prof):
    # representative stations
    picks=[("0P0077","I-695 Baltimore Beltway"),("0P0051","I-95"),
           ("0P0052","I-83 (N of I-695)"),("0P0038","MD-100 (arterial)")]
    fig,axes=plt.subplots(2,2,figsize=(8.4,6.0),sharex=True)
    hrs=np.arange(24)
    for ax,(sid,name) in zip(axes.flat,picks):
        r=prof[prof.station_id==sid]
        if len(r)==0: ax.set_visible(False); continue
        r=r.iloc[0]
        obs=[r[f"obs_h{h}"] for h in hrs]; mod=[r[f"mod_h{h}"] for h in hrs]
        ymax=max(max(obs),max(mod))*1.1
        ax.plot(hrs,obs,"-o",ms=3,lw=1.4,color=trb_style.OBS,label="TMAS observed")
        ax.plot(hrs,mod,"-s",ms=3,lw=1.4,color=trb_style.SIM,label=r"MATSim $\times$10")
        ax.fill_between([6.5,9.5],0,ymax,color=trb_style.NEUTRAL,alpha=0.06)
        ax.fill_between([15.5,18.5],0,ymax,color=trb_style.NEUTRAL,alpha=0.06)
        ax.set_title(f"{name}  (station {sid})",fontsize=9.5)
        ax.set_xlim(0,23); ax.set_ylim(0,ymax)
        ax.grid(True,ls=":",lw=0.3,alpha=0.5)
        if ax in axes[:,0]: ax.set_ylabel("veh/hour (both dir.)")
        if ax in axes[1,:]: ax.set_xlabel("Hour of day")
    axes[0,0].legend(frameon=False,loc="upper left",fontsize=8)
    fig.tight_layout(rect=[0,0.03,1,1])
    trb_style.save(fig, FIG/"d_hourly_profiles",
        "Figure 4. Weekday hourly volume profiles at representative stations: simulated MATSim (×10) vs. FHWA TMAS 2023.")
    print("wrote d_hourly_profiles.png/.pdf")

if __name__=="__main__":
    d=pd.read_csv(OUTDIR/"aadt/aadt_validation_2023.csv")
    prof=pd.read_csv(OUTDIR/"tmas/station_profiles.csv")
    fig_scatter(d); fig_geh_dist(d); fig_ratio_box(d); fig_hourly(prof)
    print("all figures ->", FIG)
