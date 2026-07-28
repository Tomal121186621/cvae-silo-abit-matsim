#!/usr/bin/env python3
"""Generate the SILO model-performance figure suite into this folder.

Reads validation summaries (per-year TV vs ACS, 6 states) and produces:
  01_meanTV_by_state_year        - accuracy over time, calib/forecast windows shaded
  02_error_decomposition         - base-year (VAE) vs drift (SILO) per state
  03_income_bias_by_year         - HH median income bias over time
  04_forecast_skill_by_state     - calib(in-sample) vs forecast(out-of-sample) [needs framework]
  05_forecast_vs_baseline        - framework forecast skill vs free-run baseline [needs framework]
  06_forecast_per_variable       - per-variable out-of-sample TV heatmap [needs framework]

Usage: python make_performance_figures.py
(reads ../validation/_incomefix_FULL_summary.csv as baseline/free-run, and
 ../validation/by_year_acs_fcast/summary.csv as the calibrate-forecast framework run if present.)
"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd, numpy as np
from pathlib import Path

HERE=Path(__file__).resolve().parent; VAL=HERE.parent/"validation"; FIG=VAL/"figures"; FIG.mkdir(parents=True,exist_ok=True)
TV=["hhSize","autos","dwellingType","hh_inc9","age_bin","gender","race4","occ_silo"]
STATES=["MD","VA","PA","DE","WV","DC"]; COL={"MD":"#4C72B0","VA":"#55A868","PA":"#8172B3","DE":"#CCB974","WV":"#C44E52","DC":"#000000"}
CALIB=list(range(2016,2021)); FORE=[2021,2022,2023]
plt.rcParams.update({"savefig.dpi":150,"font.size":11,"axes.grid":True,"grid.alpha":0.25})

base=pd.read_csv(VAL/"_incomefix_FULL_summary.csv")
fcast_p=VAL/"by_year_acs_fcast"/"summary.csv"
fcast=pd.read_csv(fcast_p) if fcast_p.exists() else None

def mtv(df,st,yrs=range(2016,2024)):
    d=df[(df.state==st)&(df.variable.isin(TV))&(df.year.isin(list(yrs)))]
    return d.groupby("year").tv.mean()

def shade(ax):
    ax.axvspan(2015.5,2020.5,color="#E8F0FE",alpha=.5,zorder=0,label="calibrate")
    ax.axvspan(2020.5,2023.5,color="#FFF0E0",alpha=.6,zorder=0,label="forecast")

# 01 mean TV by state over years (baseline)
fig,ax=plt.subplots(figsize=(11,6)); shade(ax)
for st in STATES:
    s=mtv(base,st); ax.plot(s.index,s.values,"o-",color=COL[st],lw=2,ms=4,label=st)
ax.set_title("Model accuracy over time (free-run baseline): mean TV vs ACS, by state"); ax.set_ylabel("mean TV (lower=better)")
ax.axhline(0.05,ls="--",c="grey",alpha=.6); ax.legend(ncol=4,fontsize=9); ax.set_xlabel("year")
fig.tight_layout(); fig.savefig(FIG/"01_meanTV_by_state_year.png",bbox_inches="tight"); plt.close()

# 02 error decomposition base vs drift
fig,ax=plt.subplots(figsize=(11,6)); x=np.arange(len(STATES)); w=0.38
b0=[mtv(base,st).get(2016,np.nan) for st in STATES]; b3=[mtv(base,st).get(2023,np.nan) for st in STATES]
drift=[e-b for b,e in zip(b0,b3)]
ax.bar(x-w/2,b0,w,label="base-year 2016 (VAE)",color="#4C72B0")
ax.bar(x+w/2,drift,w,bottom=b0,label="drift 2016->2023 (SILO)",color="#DD8452")
ax.axhline(0.05,ls="--",c="grey"); ax.set_xticks(x); ax.set_xticklabels(STATES); ax.set_ylabel("mean TV")
ax.set_title("Error decomposition: VAE base vs SILO drift (free-run)"); ax.legend()
fig.tight_layout(); fig.savefig(FIG/"02_error_decomposition.png",bbox_inches="tight"); plt.close()

# 03 income bias
fig,ax=plt.subplots(figsize=(11,6)); shade(ax)
for st in STATES:
    d=base[(base.state==st)&(base.variable=="income_median_bias_pct")].set_index("year").tv
    ax.plot(d.index,d.values,"o-",color=COL[st],lw=2,ms=4,label=st)
ax.axhline(0,c="k",lw=.8); ax.axhline(5,ls=":",c="grey"); ax.axhline(-5,ls=":",c="grey")
ax.set_title("HH median income bias vs ACS (free-run baseline)"); ax.set_ylabel("bias %"); ax.legend(ncol=4,fontsize=9)
fig.tight_layout(); fig.savefig(FIG/"03_income_bias_by_year.png",bbox_inches="tight"); plt.close()
n=3

# Framework figures (calibrate-forecast)
if fcast is not None:
    n=6
    # 04 calib vs forecast per state
    fig,ax=plt.subplots(figsize=(11,6)); x=np.arange(len(STATES)); w=0.38
    cal=[mtv(fcast,st,CALIB).mean() for st in STATES]; fo=[mtv(fcast,st,FORE).mean() for st in STATES]
    ax.bar(x-w/2,cal,w,label="calibration 2016-2020 (in-sample)",color="#4C72B0")
    ax.bar(x+w/2,fo,w,label="forecast 2021-2023 (OUT-OF-SAMPLE)",color="#C44E52")
    ax.axhline(0.05,ls="--",c="grey"); ax.set_xticks(x); ax.set_xticklabels(STATES); ax.set_ylabel("mean TV")
    ax.set_title("Calibrate vs Forecast performance (framework): out-of-sample = true skill"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG/"04_forecast_skill_by_state.png",bbox_inches="tight"); plt.close()
    # 05 framework forecast vs baseline forecast
    fig,ax=plt.subplots(figsize=(11,6));
    bf=[mtv(base,st,FORE).mean() for st in STATES]; ff=[mtv(fcast,st,FORE).mean() for st in STATES]
    ax.bar(x-w/2,bf,w,label="free-run baseline forecast",color="#999999")
    ax.bar(x+w/2,ff,w,label="calibrate-forecast framework",color="#55A868")
    ax.set_xticks(x); ax.set_xticklabels(STATES); ax.set_ylabel("forecast mean TV (2021-2023)")
    ax.set_title("Forecast skill: framework vs free-run baseline (lower=better)"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG/"05_forecast_vs_baseline.png",bbox_inches="tight"); plt.close()
    # 06 per-variable forecast heatmap
    M=np.full((len(TV),len(STATES)),np.nan)
    for j,st in enumerate(STATES):
        for i,v in enumerate(TV):
            d=fcast[(fcast.state==st)&(fcast.variable==v)&(fcast.year.isin(FORE))]
            if len(d): M[i,j]=d.tv.mean()
    fig,ax=plt.subplots(figsize=(9,7)); im=ax.imshow(M,cmap="RdYlGn_r",vmin=0,vmax=0.15,aspect="auto")
    ax.set_xticks(range(len(STATES))); ax.set_xticklabels(STATES); ax.set_yticks(range(len(TV))); ax.set_yticklabels(TV)
    for i in range(len(TV)):
        for j in range(len(STATES)):
            if not np.isnan(M[i,j]): ax.text(j,i,f"{M[i,j]:.3f}",ha="center",va="center",fontsize=8)
    ax.set_title("Out-of-sample forecast TV per variable x state (2021-2023)"); fig.colorbar(im,label="TV")
    fig.tight_layout(); fig.savefig(FIG/"06_forecast_per_variable.png",bbox_inches="tight"); plt.close()

# pull in the diagnostic figures already made
import shutil
for f in ["_ROOTCAUSE_trends.png","_OVERVIEW_6state.png","_DC_fix_comparison.png"]:
    src=VAL/f
    if not src.exists(): src=VAL/"by_year_acs_allstates"/f
    if src.exists(): shutil.copy2(src,FIG/("diag_"+f.lstrip("_")))
print(f"generated {n} core figures + diagnostics in {FIG}")
print("framework forecast figures:", "YES" if fcast is not None else "PENDING (run validate on updated_vae_fcast first)")
