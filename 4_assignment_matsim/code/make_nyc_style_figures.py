#!/usr/bin/env python3
"""NYC-paper-style validation figure set (He, Chow, Ozbay et al., Transport Policy).

(a) link-count scatter sim-vs-obs with median/avg relative-difference annotation (their 29%/39.8%)
(b) screenline volume sim-vs-obs by 6 time periods (their Fig. 16, East-River screenline)
(c) transit ridership sim-vs-obs by mode (their Table 5, subway stations)
(d) speed by period -- only if an observed speed source (INRIX/HERE) is present; else a note panel.

Times, 600 dpi, PNG + PDF -> network_validation_2023/figures_nyc_style/.
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from netval2023_common import OUTDIR

plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":10,"axes.titlesize":11,"axes.labelsize":10,
    "legend.fontsize":8.5,"xtick.labelsize":9,"ytick.labelsize":9,
    "axes.linewidth":0.7,"savefig.dpi":600,"figure.dpi":120,
})
FIG=OUTDIR/"figures_nyc_style"; FIG.mkdir(parents=True,exist_ok=True)
SIMCOL="#2E5C8A"; OBSCOL="#D46A1E"

def save(fig,name):
    fig.savefig(FIG/f"{name}.png",bbox_inches="tight")
    fig.savefig(FIG/f"{name}.pdf",bbox_inches="tight")
    plt.close(fig); print("wrote",name+".png/.pdf")

# ---------------------------------------------------------------- (a) link scatter
def fig_a():
    d=pd.read_csv(OUTDIR/"aadt/aadt_validation_2023.csv")
    d=d[(d.model_daily>0)&(d.facility!="Ramp")].copy()   # mainline like NYC's 42 selected links
    rel=np.abs(d.model_daily-d.obs_AADT)/d.obs_AADT*100
    avg=rel.mean(); med=rel.median()
    corr2=np.corrcoef(d.obs_AADT,d.model_daily)[0,1]**2
    maj=d[d.facility.isin(["Interstate/Freeway","Principal Arterial"])]
    mrel=np.abs(maj.model_daily-maj.obs_AADT)/maj.obs_AADT*100
    mavg,mmed=mrel.mean(),mrel.median()
    fig,ax=plt.subplots(figsize=(5.4,5.2))
    lo,hi=500,4e5
    ax.plot([lo,hi],[lo,hi],"k--",lw=0.9,zorder=2,label="1:1 line")
    ax.scatter(d.obs_AADT,d.model_daily,s=8,c=SIMCOL,alpha=0.35,edgecolors="none",zorder=3)
    ax.set_xscale("log");ax.set_yscale("log");ax.set_xlim(lo,hi);ax.set_ylim(lo,hi)
    ax.set_xlabel("Observed count (AADT 2023, veh/day)")
    ax.set_ylabel(r"Simulated volume (MATSim $\times$10, veh/day)")
    ax.set_title("Link-count validation: simulated vs observed")
    txt=(f"all mainline (n={len(d):,}):\n"
         f"  avg |rel|={avg:.0f}%  median={med:.0f}%\n"
         f"major fwy+principal (n={len(maj):,}):\n"
         f"  avg |rel|={mavg:.0f}%  median={mmed:.0f}%\n"
         r"corr$^2$ = "+f"{corr2:.2f}")
    ax.text(0.04,0.96,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4",fc="white",ec="#888",alpha=0.92))
    ax.text(0.97,0.06,"NYC ref (He et al.):\navg 39.8% · median 29%",transform=ax.transAxes,
            va="bottom",ha="right",fontsize=7.5,style="italic",color="#555")
    ax.legend(loc="lower right",frameon=True,bbox_to_anchor=(1.0,0.16))
    ax.grid(True,which="both",ls=":",lw=0.3,alpha=0.5)
    save(fig,"a_linkcount_scatter")
    return avg,med,corr2

# ---------------------------------------------------------------- (b) screenline by period
def fig_b():
    p=pd.read_csv(OUTDIR/"screenline_by_period.csv")
    sub=p[p.screenline.str.startswith("Named")].copy()
    if sub.empty: sub=p[p.screenline.str.startswith("Full")].copy()
    order=["6-9AM","9AM-12PM","12-3PM","3-6PM","6-9PM","9PM-6AM"]
    sub["period"]=pd.Categorical(sub.period,order,ordered=True); sub=sub.sort_values("period")
    x=np.arange(len(sub)); w=0.38
    fig,ax=plt.subplots(figsize=(6.6,3.9))
    ax.bar(x-w/2,sub.obs,w,color=OBSCOL,label="observed (AADT-distributed)")
    ax.bar(x+w/2,sub.model,w,color=SIMCOL,label=r"simulated (MATSim $\times$10)")
    for xi,dp in zip(x,sub.diff_pct): ax.text(xi,max(sub.obs.iloc[0],1)*0.02,f"{dp:+.0f}%",ha="center",va="bottom",fontsize=7.5,color="#333")
    ax.set_xticks(x);ax.set_xticklabels(order,rotation=0,fontsize=8.5)
    ax.set_ylabel("Screenline volume (veh)")
    tot=(sub.model.sum()-sub.obs.sum())/sub.obs.sum()*100
    ax.set_title(f"Baltimore Beltway screenline by period  (total daily {tot:+.0f}%)")
    ax.legend(frameon=True,loc="upper right"); ax.grid(True,axis="y",ls=":",lw=0.3,alpha=0.5)
    ax.text(0.01,0.97,"NYC East-River ref: +1.8% (SPSA-calibrated, all traffic)",transform=ax.transAxes,
            va="top",ha="left",fontsize=7,style="italic",color="#666")
    save(fig,"b_screenline_by_period")

# ---------------------------------------------------------------- (c) transit ridership
def fig_c():
    f=OUTDIR/"transit/transit_validation_2023.csv"
    if not f.exists():
        print("(c) skipped: transit/transit_validation_2023.csv not present yet"); return
    t=pd.read_csv(f)
    # expected cols: mode, observed_weekday, sim_daily_x10, diff_pct
    oc=[c for c in t.columns if "obs" in c.lower()][0]
    sc=[c for c in t.columns if "sim" in c.lower()][0]
    t=t[t[oc].notna() & ~t["mode"].str.startswith(("TOTAL","AVG"))].copy()
    t["mode"]=t["mode"].str.replace(r"\s*\(.*\)","",regex=True)   # short labels
    x=np.arange(len(t)); w=0.38
    fig,ax=plt.subplots(figsize=(6.6,4.0))
    ax.bar(x-w/2,t[oc],w,color=OBSCOL,label="observed (NTD/MTA weekday)")
    ax.bar(x+w/2,t[sc],w,color=SIMCOL,label=r"simulated (MATSim $\times$10)")
    dpc=[c for c in t.columns if "diff" in c.lower()]
    if dpc:
        for xi,dp,sv in zip(x,t[dpc[0]],t[sc]):
            if pd.notna(dp): ax.text(xi,sv*1.25,f"{dp:+.0f}%",ha="center",va="bottom",fontsize=7.5,color="#333")
    ax.set_yscale("log"); ax.set_ylim(2e3,1e6)
    ax.set_xticks(x);ax.set_xticklabels(t["mode"],rotation=20,ha="right",fontsize=8.5)
    ax.set_ylabel("Daily boardings / UPT (log scale)")
    avgabs=t[dpc[0]].abs().mean() if dpc else np.nan
    ax.set_title(f"Transit ridership by mode  (sim OVER-predicts, avg |diff| {avgabs:.0f}%)" if np.isfinite(avgabs) else "Transit ridership by mode")
    ax.legend(frameon=True,loc="upper right"); ax.grid(True,axis="y",ls=":",lw=0.3,alpha=0.5)
    ax.text(0.01,0.97,"NYC subway-station ref (Table 5): 8% avg",transform=ax.transAxes,
            va="top",ha="left",fontsize=7,style="italic",color="#666")
    save(fig,"c_transit_ridership")

# ---------------------------------------------------------------- (d) speed by period
def fig_d():
    """NPMRDS observed vs simulated speed by 6 periods (He et al. Fig 15).

    Real figure once BOTH network_validation_2023/speed/{observed,simulated}_speed_2023.csv
    exist (produced by calibrate_speed_2023.py on the NPMRDS export + validate_speed_2023.py
    on the calibrated run's events). Until the NPMRDS pull lands, an explicit note panel.
    """
    sdir=OUTDIR/"speed"
    obs_csv=sdir/"observed_speed_2023.csv"; sim_csv=sdir/"simulated_speed_2023.csv"
    from speed_common import PERIOD_ORDER
    if obs_csv.exists() and sim_csv.exists():
        from validate_speed_2023 import make_figure
        obs=pd.read_csv(obs_csv,index_col=0).reindex(index=["freeway","arterial"],columns=PERIOD_ORDER)
        sim=pd.read_csv(sim_csv,index_col=0).reindex(index=["freeway","arterial"],columns=PERIOD_ORDER)
        fwy_d,art_d=make_figure(obs,sim,"2023",FIG)
        print(f"wrote d_speed_by_period.png/.pdf  (freeway {fwy_d:.1f}%, arterial {art_d:.1f}%)")
        return
    # NPMRDS not yet pulled -> explicit note panel (shows computed simulated speeds if present)
    simnote=""
    if sim_csv.exists():
        s=pd.read_csv(sim_csv,index_col=0)
        simnote=("\nSimulated speeds ARE computed (network_validation_2023/speed/"
                 "simulated_speed_2023.csv);\nawaiting the NPMRDS observed table to complete the comparison.")
    fig,ax=plt.subplots(figsize=(6.6,3.4)); ax.axis("off")
    ax.text(0.5,0.5,"(d) Speed-by-period validation pending NPMRDS 2023 pull.\n\n"
            "Calibration + validation code is ready (calibrate_speed_2023.py / validate_speed_2023.py).\n"
            "NPMRDS (free, RITIS/CATT-Lab, UMD access) must be exported interactively —\n"
            "see data/npmrds_2023/README_ACCESS.md. FHWA TMAS 2023 gives volumes, not speeds."
            +simnote+
            "\nNYC ref (He et al. Fig. 15): freeway 7.2% avg, arterial 17.1% avg vs INRIX.",
            ha="center",va="center",fontsize=9,color="#333",
            bbox=dict(boxstyle="round,pad=0.7",fc="#f5f5f5",ec="#aaa"))
    save(fig,"d_speed_by_period_UNAVAILABLE")

if __name__=="__main__":
    a=fig_a(); fig_b(); fig_c(); fig_d()
    print(f"\nlink-count: avg|rel|={a[0]:.1f}%  median|rel|={a[1]:.1f}%  corr2={a[2]:.2f}")
    print("figures ->",FIG)
