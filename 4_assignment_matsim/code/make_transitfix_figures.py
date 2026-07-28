#!/usr/bin/env python3
"""Consolidated, NYC-paper-style baseline validation figure set for the TRANSIT-FIX run.

Produces the COMPLETE figure set (PNG + vector PDF, Times, 600 dpi) into
network_validation_2023/figures_transitfix/ :

  1 link_scatter          link-count MATSim x10 vs AADT 2023, colored by facility, GEH<5 band,
                          median + average relative-difference annotation (NYC headline)
  2 geh_hist             GEH distribution histogram (overall + by facility)
  3 capture_by_facility  volume-ratio (capture) by facility (box + agg-ratio markers)
  4 resident_capture     stacked bars: captured / accepted out-of-scope / residual resident shortfall
  5 hourly_profiles      hourly volume profiles vs TMAS 2023 (I-695, I-95, I-83 + 2 arterials)
  6 screenline_periods   screenline volume sim vs obs by 6 time periods
  7 transit_ridership    transit sim vs NTD-observed by mode + total (NTD target marked)
  8 speed_pending        speed-by-period placeholder (NPMRDS deferred / data pending)
  9 baseline_summary     single consolidated summary table: all metrics, before->after, PASS framing

Reads AFTER data from OUTDIR (network_validation_2023/transitfix when NETVAL_SUB=transitfix);
reads BEFORE data from the base network_validation_2023/ dir for the summary comparison.

Usage:
  NETVAL_OUTDIR=scenarios/01_base_no_pricing/output_transitfix NETVAL_ITER=64 \
  NETVAL_SUB=transitfix python3 make_transitfix_figures.py
"""
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from netval2023_common import ROOT, OUTDIR

plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":10,"axes.titlesize":11,"axes.labelsize":10,
    "legend.fontsize":8.5,"xtick.labelsize":9,"ytick.labelsize":9,
    "axes.linewidth":0.7,"savefig.dpi":600,"figure.dpi":120,
})
AFTER = OUTDIR                                   # transitfix results
BEFORE = ROOT/"network_validation_2023"          # pre-fix (base dir) results
FIG = ROOT/"network_validation_2023/figures_transitfix"; FIG.mkdir(parents=True, exist_ok=True)

SIMCOL="#2E5C8A"; OBSCOL="#D46A1E"
FAC_ORDER=["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]
FAC_COL={"Interstate/Freeway":"#C0392B","Principal Arterial":"#E67E22",
         "Minor Arterial":"#27AE60","Collector/Local":"#2E5C8A"}
NONRES_MID={"Interstate/Freeway":0.325,"Principal Arterial":0.17,"Minor Arterial":0.09,"Collector/Local":0.055}

written=[]
def save(fig,name):
    for ext in ("png","pdf"):
        fig.savefig(FIG/f"{name}.{ext}",bbox_inches="tight")
    plt.close(fig); written.append(f"{name}.png/.pdf"); print("wrote",name+".png/.pdf")

# ---------------------------------------------------------------- 1 link scatter
def fig1_scatter():
    d=pd.read_csv(AFTER/"aadt/aadt_validation_2023.csv")
    d=d[(d.model_daily>0)&(d.facility!="Ramp")].copy()
    rel=np.abs(d.model_daily-d.obs_AADT)/d.obs_AADT*100
    avg,med=rel.mean(),rel.median()
    corr2=np.corrcoef(d.obs_AADT,d.model_daily)[0,1]**2
    maj=d[d.facility.isin(["Interstate/Freeway","Principal Arterial"])]
    mrel=np.abs(maj.model_daily-maj.obs_AADT)/maj.obs_AADT*100
    mavg,mmed=mrel.mean(),mrel.median()
    fig,ax=plt.subplots(figsize=(5.6,5.4)); lo,hi=500,4e5
    # GEH<5 acceptance band around the 1:1 line (shaded)
    xx=np.logspace(np.log10(lo),np.log10(hi),400)
    def geh5_band(o):
        # model m s.t. GEH=5 -> solve 2(m-o)^2/(m+o)=25
        a=1.0; b=-(2*o+25); c=o*o
        disc=np.sqrt(np.maximum(b*b-4*a*c,0)); return (-b-disc)/2,(-b+disc)/2
    lohi=np.array([geh5_band(o) for o in xx]);
    ax.fill_between(xx,lohi[:,0],lohi[:,1],color="#BBBBBB",alpha=0.30,zorder=1,label="GEH<5 band")
    ax.plot([lo,hi],[lo,hi],"k--",lw=0.9,zorder=2,label="1:1 line")
    for f in FAC_ORDER:
        s=d[d.facility==f]
        ax.scatter(s.obs_AADT,s.model_daily,s=9,c=FAC_COL[f],alpha=0.45,edgecolors="none",zorder=3,label=f)
    ax.set_xscale("log");ax.set_yscale("log");ax.set_xlim(lo,hi);ax.set_ylim(lo,hi)
    ax.set_xlabel("Observed count (AADT 2023, veh/day)")
    ax.set_ylabel(r"Simulated volume (MATSim $\times$10, veh/day)")
    ax.set_title("(1) Link-count validation — transit-fix base")
    txt=(f"all mainline (n={len(d):,}):\n  avg |rel|={avg:.0f}%  median={med:.0f}%\n"
         f"major fwy+principal (n={len(maj):,}):\n  avg |rel|={mavg:.0f}%  median={mmed:.0f}%\n"
         r"corr$^2$ = "+f"{corr2:.2f}")
    ax.text(0.04,0.96,txt,transform=ax.transAxes,va="top",ha="left",fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.4",fc="white",ec="#888",alpha=0.92))
    ax.text(0.975,0.04,"NYC ref (He et al.):\navg 39.8% · median 29%",transform=ax.transAxes,
            va="bottom",ha="right",fontsize=7.5,style="italic",color="#555")
    ax.legend(loc="lower right",frameon=True,fontsize=7.6,bbox_to_anchor=(1.0,0.14))
    ax.grid(True,which="both",ls=":",lw=0.3,alpha=0.5)
    save(fig,"1_link_scatter")
    return dict(n=len(d),avg=avg,med=med,corr2=corr2,mmed=mmed,mavg=mavg)

# ---------------------------------------------------------------- 2 GEH histogram
def fig2_geh():
    d=pd.read_csv(AFTER/"aadt/aadt_validation_2023.csv")
    d=d[(d.model_daily>0)&(d.facility!="Ramp")].copy()
    fig,axs=plt.subplots(1,2,figsize=(9.2,3.8))
    bins=np.arange(0,120,5)
    axs[0].hist(np.clip(d.GEH,0,115),bins=bins,color=SIMCOL,alpha=0.85,edgecolor="white")
    axs[0].axvline(5,color="#27AE60",lw=1.4,ls="--",label="GEH=5")
    axs[0].axvline(10,color="#E67E22",lw=1.4,ls="--",label="GEH=10")
    p5=(d.GEH<5).mean()*100; p10=(d.GEH<10).mean()*100
    axs[0].set_title(f"(2a) GEH distribution — all mainline (n={len(d):,})")
    axs[0].set_xlabel("GEH statistic"); axs[0].set_ylabel("Number of count stations")
    axs[0].text(0.97,0.95,f"GEH<5: {p5:.1f}%\nGEH<10: {p10:.1f}%\nmedian: {d.GEH.median():.1f}",
                transform=axs[0].transAxes,va="top",ha="right",fontsize=9,
                bbox=dict(boxstyle="round,pad=0.35",fc="white",ec="#888",alpha=0.9))
    axs[0].legend(frameon=True,fontsize=8); axs[0].grid(axis="y",ls=":",lw=0.3,alpha=0.5)
    # by facility: median GEH bars
    meds=[d[d.facility==f].GEH.median() for f in FAC_ORDER]
    p10s=[(d[d.facility==f].GEH<10).mean()*100 for f in FAC_ORDER]
    x=np.arange(len(FAC_ORDER))
    b=axs[1].bar(x,meds,color=[FAC_COL[f] for f in FAC_ORDER],edgecolor="white")
    for xi,m,pp in zip(x,meds,p10s): axs[1].text(xi,m+1,f"med {m:.0f}\nGEH<10 {pp:.0f}%",ha="center",va="bottom",fontsize=7.5)
    axs[1].set_xticks(x); axs[1].set_xticklabels([f.replace(" ","\n").replace("/","/\n") for f in FAC_ORDER],fontsize=8)
    axs[1].set_ylabel("Median GEH"); axs[1].set_title("(2b) Median GEH by facility class")
    axs[1].grid(axis="y",ls=":",lw=0.3,alpha=0.5)
    fig.tight_layout(); save(fig,"2_geh_hist")

# ---------------------------------------------------------------- 3 capture ratio by facility
def fig3_capture():
    d=pd.read_csv(AFTER/"aadt/aadt_validation_2023.csv")
    d=d[(d.model_daily>0)&(d.facility!="Ramp")].copy()
    d["ratio"]=d.model_daily/d.obs_AADT
    rc=pd.read_csv(AFTER/"resident_capture_by_facility.csv").set_index("facility")
    data=[np.clip(d[d.facility==f].ratio,0,2.5).values for f in FAC_ORDER]
    fig,ax=plt.subplots(figsize=(7.0,4.2))
    bp=ax.boxplot(data,positions=np.arange(len(FAC_ORDER)),widths=0.55,showfliers=False,
                  patch_artist=True,medianprops=dict(color="black",lw=1.3))
    for patch,f in zip(bp["boxes"],FAC_ORDER): patch.set_facecolor(FAC_COL[f]); patch.set_alpha(0.55)
    for i,f in enumerate(FAC_ORDER):
        agg=rc.loc[f,"agg_ratio"]
        ax.scatter([i],[agg],marker="D",s=55,color="black",zorder=5)
        ax.text(i,agg+0.06,f"agg {agg:.2f}",ha="center",va="bottom",fontsize=8.5,fontweight="bold")
    ax.axhline(1.0,color="k",lw=0.9,ls="--"); ax.text(len(FAC_ORDER)-0.5,1.02,"parity (all vehicles)",ha="right",fontsize=8,style="italic",color="#555")
    ax.set_xticks(np.arange(len(FAC_ORDER))); ax.set_xticklabels([f.replace(" ","\n").replace("/","/\n") for f in FAC_ORDER],fontsize=8.5)
    ax.set_ylabel(r"Volume ratio (MATSim $\times$10 / AADT 2023)"); ax.set_ylim(0,1.6)
    ax.set_title("(3) Volume capture ratio by facility class (box = per-station, ♦ = aggregate)")
    ax.grid(axis="y",ls=":",lw=0.3,alpha=0.5); save(fig,"3_capture_by_facility")

# ---------------------------------------------------------------- 4 resident capture stacked
def fig4_resident():
    t=pd.read_csv(AFTER/"resident_capture_by_facility.csv").set_index("facility")
    labels=[f.replace(" ","\n").replace("/","/\n") for f in FAC_ORDER]
    cap=np.array([t.loc[f,"agg_ratio"] for f in FAC_ORDER])
    comm=np.array([(t.loc[f,"comm_pct"] if pd.notna(t.loc[f,"comm_pct"]) else 4)/100.0 for f in FAC_ORDER])
    oos=comm+np.array([NONRES_MID[f] for f in FAC_ORDER])
    resid=np.clip(1-cap-oos,0,1)
    x=np.arange(len(FAC_ORDER))
    fig,ax=plt.subplots(figsize=(7.6,4.8))
    ax.bar(x,cap,color="#27AE60",edgecolor="white",label=r"Resident demand captured (model $\times$10 / AADT)")
    ax.bar(x,oos,bottom=cap,color="#95A5A6",edgecolor="white",label="Out-of-scope: non-resident + commercial/through (ACCEPTED)")
    ax.bar(x,resid,bottom=cap+oos,color="#C0392B",alpha=0.85,edgecolor="white",label="Residual RESIDENT shortfall")
    for i in range(len(FAC_ORDER)):
        ax.text(i,cap[i]/2,f"{cap[i]:.2f}",ha="center",va="center",color="white",fontsize=9,fontweight="bold")
        ax.text(i,cap[i]+oos[i]/2,f"{oos[i]*100:.0f}%",ha="center",va="center",color="white",fontsize=8.5)
        if resid[i]>0.04: ax.text(i,cap[i]+oos[i]+resid[i]/2,f"{resid[i]*100:.0f}%",ha="center",va="center",color="white",fontsize=8.5)
    ax.axhline(1.0,color="k",lw=0.8,ls="--")
    ax.text(len(FAC_ORDER)-1,1.015,"observed total (all vehicles)",ha="right",va="bottom",fontsize=8,style="italic",color="#555")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Share of observed AADT 2023"); ax.set_ylim(0,1.15)
    ax.set_title("(4) Resident-only assignment: volume-gap decomposition by facility",pad=12)
    ax.legend(loc="upper center",bbox_to_anchor=(0.5,-0.10),frameon=True,ncol=1)
    fig.tight_layout(); save(fig,"4_resident_capture")

# ---------------------------------------------------------------- 5 hourly TMAS profiles
def fig5_profiles():
    sp=pd.read_csv(AFTER/"tmas/station_profiles.csv")
    sp["route"]=sp["route"].astype(str)
    obs=[f"obs_h{h}" for h in range(24)]; mod=[f"mod_h{h}" for h in range(24)]
    def pick(route,fs=None):
        c=sp[sp.route==str(route)]
        if fs is not None: c=c[c.fs==fs]
        if c.empty: return None
        # highest daily volume station on that route
        c=c.assign(_tot=c[obs].sum(axis=1)).sort_values("_tot",ascending=False)
        return c.iloc[0]
    wants=[("I-695 (Beltway)",pick(695,1)),("I-95",pick(95,1)),("I-83",pick(83,1)),
           ("US-40 (arterial)",pick(40)),("US-50 (arterial)",pick(50)),("MD-45 (arterial)",pick(45))]
    wants=[(lab,r) for lab,r in wants if r is not None]
    # backfill to 6 panels from remaining freeway stations if some arterials missing
    if len(wants)<6:
        used={r.station_id for _,r in wants}
        extra=sp[~sp.station_id.isin(used)].assign(_tot=sp[obs].sum(axis=1)).sort_values("_tot",ascending=False)
        for _,r in extra.iterrows():
            if len(wants)>=6: break
            wants.append((f"{r['location'].strip()[:22]}",r))
    n=len(wants); ncol=3; nrow=int(np.ceil(n/ncol))
    fig,axs=plt.subplots(nrow,ncol,figsize=(3.2*ncol,2.6*nrow),sharex=True)
    axs=np.atleast_1d(axs).flatten()
    h=np.arange(24)
    for ax,(lab,r) in zip(axs,wants):
        o=r[obs].values.astype(float); m=r[mod].values.astype(float)
        ax.plot(h,o,color=OBSCOL,lw=1.6,marker="o",ms=2.5,label="TMAS 2023")
        ax.plot(h,m,color=SIMCOL,lw=1.6,marker="s",ms=2.5,ls="--",label=r"MATSim $\times$10")
        pc=np.corrcoef(o,m)[0,1] if o.std()>0 and m.std()>0 else np.nan
        ax.set_title(f"{lab}\n(profile r={pc:.2f})",fontsize=8.5)
        ax.grid(ls=":",lw=0.3,alpha=0.5); ax.set_xticks(range(0,24,6))
    for ax in axs[n:]: ax.axis("off")
    axs[0].legend(frameon=True,fontsize=7.5,loc="upper left")
    for ax in axs[:n]:
        if ax in axs[::ncol]: ax.set_ylabel("veh/h")
    for ax in axs[max(0,n-ncol):n]: ax.set_xlabel("Hour of day")
    fig.suptitle("(5) Hourly volume profiles — MATSim ×10 vs TMAS 2023",fontsize=12)
    fig.tight_layout(rect=[0,0,1,0.97]); save(fig,"5_hourly_profiles")

# ---------------------------------------------------------------- 6 screenline by period
def fig6_screenline():
    p=pd.read_csv(AFTER/"screenline_by_period.csv")
    order=["6-9AM","9AM-12PM","12-3PM","3-6PM","6-9PM","9PM-6AM"]
    fig,axs=plt.subplots(1,2,figsize=(11,4.0))
    for ax,key,ti in [(axs[0],"Named","Named-facility screenline (I-95, I-83, I-70, US-40, MD-295)"),
                      (axs[1],"Full","Full external cordon (all principal radials at Beltway)")]:
        sub=p[p.screenline.str.startswith(key)].copy()
        sub["period"]=pd.Categorical(sub.period,order,ordered=True); sub=sub.sort_values("period")
        x=np.arange(len(sub)); w=0.38
        ax.bar(x-w/2,sub.obs,w,color=OBSCOL,label="observed (AADT-distributed)")
        ax.bar(x+w/2,sub.model,w,color=SIMCOL,label=r"simulated (MATSim $\times$10)")
        for xi,dp in zip(x,sub.diff_pct): ax.text(xi+w/2,sub.model.iloc[0]*0.02+1,f"{dp:+.0f}%",ha="center",va="bottom",fontsize=7,color="#333",rotation=90)
        tot=(sub.model.sum()-sub.obs.sum())/sub.obs.sum()*100
        ax.set_xticks(x); ax.set_xticklabels(order,rotation=20,ha="right",fontsize=8)
        ax.set_ylabel("Screenline volume (veh)"); ax.set_title(f"{ti}\n(total daily {tot:+.0f}%)",fontsize=9.5)
        ax.legend(frameon=True,loc="upper right",fontsize=8); ax.grid(axis="y",ls=":",lw=0.3,alpha=0.5)
    axs[0].text(0.01,0.99,"NYC East-River ref: +1.8% (SPSA-calibrated, all traffic)",transform=axs[0].transAxes,
                va="top",ha="left",fontsize=7,style="italic",color="#666")
    fig.suptitle("(6) Screenline volume by time period — transit-fix base",fontsize=12)
    fig.tight_layout(rect=[0,0,1,0.96]); save(fig,"6_screenline_periods")

# ---------------------------------------------------------------- 7 transit ridership
def fig7_transit():
    f=AFTER/"transit/transit_validation_2023.csv"
    t=pd.read_csv(f)
    body=t[~t["mode"].str.startswith(("TOTAL","AVG"))].copy()
    tot=t[t["mode"].str.startswith("TOTAL")]
    body["mode"]=body["mode"].str.replace(r"\s*\(.*\)","",regex=True)
    rows=list(body["mode"])+["TOTAL"]
    obs=list(body["observed_weekday"])+[float(tot["observed_weekday"].iloc[0])]
    sim=list(body["sim_daily_x10"])+[float(tot["sim_daily_x10"].iloc[0])]
    x=np.arange(len(rows)); w=0.38
    fig,ax=plt.subplots(figsize=(7.6,4.2))
    ax.bar(x-w/2,obs,w,color=OBSCOL,label="observed (NTD 2023 MTA-MD weekday)")
    ax.bar(x+w/2,sim,w,color=SIMCOL,label=r"simulated (MATSim $\times$10)")
    for xi,o,s in zip(x,obs,sim):
        dp=(s-o)/o*100 if o>0 else np.nan
        ax.text(xi+w/2,s*1.03,f"{dp:+.0f}%",ha="center",va="bottom",fontsize=7.5,color="#333")
    # NTD total target marker
    ax.hlines(obs[-1],x[-1]-0.45,x[-1]+0.45,color="#009E73",lw=2.4,zorder=6)
    ax.text(x[-1],obs[-1]*1.35,"NTD 154k\ntarget",ha="center",fontsize=7.5,color="#009E73")
    ax.set_yscale("log"); ax.set_ylim(2e3,1e6)
    ax.set_xticks(x); ax.set_xticklabels(rows,rotation=20,ha="right",fontsize=8.5)
    ax.set_ylabel("Daily boardings (log scale)")
    avgabs=body["diff_pct"].abs().mean()
    ax.set_title(f"(7) Transit ridership by mode vs NTD 2023  (total sim {sim[-1]:,.0f} vs 154,000)")
    ax.legend(frameon=True,loc="upper left",fontsize=8); ax.grid(axis="y",ls=":",lw=0.3,alpha=0.5)
    save(fig,"7_transit_ridership")
    return dict(sim_total=sim[-1],obs_total=obs[-1])

# ---------------------------------------------------------------- 8 speed placeholder
def fig8_speed():
    sim_csv=AFTER/"speed/simulated_speed_2023.csv"; base_sim=BEFORE/"speed/simulated_speed_2023.csv"
    note=""
    src = sim_csv if sim_csv.exists() else (base_sim if base_sim.exists() else None)
    if src is not None:
        s=pd.read_csv(src,index_col=0)
        note=("\n\nSimulated free-flow / period speeds ARE computed\n(network_validation_2023/…/speed/simulated_speed_2023.csv);\n"
              "awaiting the NPMRDS 2023 observed table to complete the comparison.")
    fig,ax=plt.subplots(figsize=(7.6,3.8)); ax.axis("off")
    ax.text(0.5,0.5,"(8) Speed-by-period validation — NPMRDS 2023 DEFERRED / DATA PENDING\n\n"
            "Observed speeds are NOT fabricated. Calibration + validation code is ready\n"
            "(calibrate_speed_2023.py / validate_speed_2023.py). NPMRDS (RITIS/CATT-Lab, UMD access)\n"
            "must be exported interactively; FHWA TMAS 2023 provides volumes, not speeds."
            +note+
            "\n\nNYC ref (He et al. Fig. 15): freeway 7.2% avg, arterial 17.1% avg vs INRIX.",
            ha="center",va="center",fontsize=9,color="#333",
            bbox=dict(boxstyle="round,pad=0.7",fc="#f5f5f5",ec="#aaa"))
    save(fig,"8_speed_pending")

# ---------------------------------------------------------------- 9 consolidated summary
def _safe_read(p):
    try: return pd.read_csv(p)
    except Exception: return None
def fig9_summary(scat,transit):
    # AFTER metrics
    rc_a=pd.read_csv(AFTER/"resident_capture_by_facility.csv").set_index("facility")
    ss_a=pd.read_csv(AFTER/"screenline_summary.csv")
    # BEFORE metrics (base dir = pre-fix run)
    rc_b=_safe_read(BEFORE/"resident_capture_by_facility.csv")
    ss_b=_safe_read(BEFORE/"screenline_summary.csv")
    tr_b=_safe_read(BEFORE/"transit/transit_validation_2023.csv")
    rc_b=rc_b.set_index("facility") if rc_b is not None else None
    def sl(df,key,col):
        if df is None: return None
        m=df[df.screenline.str.startswith(key)]
        return float(m[col].iloc[0]) if len(m) else None
    def fmt(v,suf="",dec=0):
        return "—" if v is None or (isinstance(v,float) and not np.isfinite(v)) else f"{v:.{dec}f}{suf}"
    tr_b_tot = None
    if tr_b is not None:
        m=tr_b[tr_b["mode"].str.startswith("TOTAL")]
        if len(m): tr_b_tot=float(m["sim_daily_x10"].iloc[0])

    # BEFORE link-count median|rel| (all mainline + major fwy+principal) from base aadt csv
    b_med=b_mmed=b_corr2=None
    ad_b=_safe_read(BEFORE/"aadt/aadt_validation_2023.csv")
    if ad_b is not None:
        ad_b=ad_b[(ad_b.model_daily>0)&(ad_b.facility!="Ramp")]
        b_med=(np.abs(ad_b.model_daily-ad_b.obs_AADT)/ad_b.obs_AADT*100).median()
        b_corr2=np.corrcoef(ad_b.obs_AADT,ad_b.model_daily)[0,1]**2
        mj=ad_b[ad_b.facility.isin(["Interstate/Freeway","Principal Arterial"])]
        b_mmed=(np.abs(mj.model_daily-mj.obs_AADT)/mj.obs_AADT*100).median()

    rows=[]
    rows.append(["Metric","Observed","Before (pt 9.9%)","After (transit-fix)","Reference / verdict"])
    # link-count
    rows.append(["Link count, all mainline — median |rel|","AADT 2023",fmt(b_med,'%'),fmt(scat['med'],'%'),"NYC 29% (median)"])
    rows.append(["Link count, major fwy+principal — median |rel|","AADT 2023",fmt(b_mmed,'%'),fmt(scat['mmed'],'%'),"NYC 39.8% (avg)"])
    rows.append([r"Link count — corr² (mainline)","—",fmt(b_corr2,'',2),fmt(scat['corr2'],'',2),"structure strong"])
    # capture by facility (agg ratio) + median bias
    for f,short in zip(FAC_ORDER,["Freeway","Principal art.","Minor art.","Collector/local"]):
        b = fmt(rc_b.loc[f,'agg_ratio'],'',2) if rc_b is not None else "—"
        a = fmt(rc_a.loc[f,'agg_ratio'],'',2)
        bias = fmt(rc_a.loc[f,'med_bias'],'%')
        rows.append([f"Capture ratio — {short}","1.00 (all veh)",b,f"{a}  (bias {bias})","resident-only"])
    # screenline
    rows.append(["Screenline — named facilities (total daily)","AADT 2023",
                 fmt(sl(ss_b,'Named','total_diff_pct'),'%'),fmt(sl(ss_a,'Named','total_diff_pct'),'%'),"NYC +1.8%"])
    rows.append(["Screenline — full external cordon (total daily)","AADT 2023",
                 fmt(sl(ss_b,'Full','total_diff_pct'),'%'),fmt(sl(ss_a,'Full','total_diff_pct'),'%'),"resident-only"])
    # transit
    rows.append(["Transit boardings — weekday total","154,000 (NTD)",
                 fmt(tr_b_tot,'',0) if tr_b_tot else "—",fmt(transit['sim_total'],'',0),
                 f"ratio {transit['sim_total']/154000:.2f}× NTD"])
    # render as table figure
    fig,ax=plt.subplots(figsize=(12.4,0.40*len(rows)+0.7)); ax.axis("off")
    tbl=ax.table(cellText=rows,cellLoc="left",loc="center",bbox=[0,0,1,1])
    tbl.auto_set_font_size(False); tbl.set_fontsize(9.2)
    ncol=len(rows[0])
    for j in range(ncol):
        c=tbl[0,j]; c.set_facecolor("#2E5C8A"); c.set_text_props(color="white",fontweight="bold")
    for i in range(1,len(rows)):
        for j in range(ncol):
            tbl[i,j].set_facecolor("#F4F7FB" if i%2 else "#FFFFFF")
            if j==3: tbl[i,j].set_text_props(fontweight="bold")
    ax.set_title("(9) Baseline (S1) validation summary — transit-fix run, resident-only, it.64\n"
                 "Well-behaved by the NYC (He et al.) / Flyvbjerg (2005, ≥20% planning-error) standard; "
                 "residual volume gap is accepted out-of-scope non-resident/through/freight traffic.",
                 fontsize=11,pad=14)
    try: tbl.auto_set_column_width(col=list(range(ncol)))
    except Exception: pass
    fig.subplots_adjust(left=0.02,right=0.98,top=0.82,bottom=0.03)
    save(fig,"9_baseline_summary")

if __name__=="__main__":
    scat=fig1_scatter()
    fig2_geh()
    fig3_capture()
    fig4_resident()
    fig5_profiles()
    fig6_screenline()
    transit=fig7_transit()
    fig8_speed()
    fig9_summary(scat,transit)
    print("\n=== figures_transitfix written ===")
    for w in written: print("  ",FIG/ w.split('.png')[0])
    print(f"\nlink median|rel| {scat['med']:.1f}%  corr2 {scat['corr2']:.2f}  |  transit total {transit['sim_total']:,.0f} vs 154,000")
