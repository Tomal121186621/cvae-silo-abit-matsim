#!/usr/bin/env python3
"""Per-route AADT validation figures from the CORRECTED base run (base_speedfix, it.64).

HONEST-FRAMING VERSION (TRB review CR-2 / MJ-5). This replaces the earlier
scratchpad generator `aadt_by_route.py`, which was not repo-resident and which
manufactured an "ALL mainline PASS" via an OR-gate. The changes made here:

  1. NO OR-gate PASS. There is no fabricated pass/fail column. Each criterion
     (GEH<5%, %-in-band, corr², true R², median bias) is reported on its own.
     The mainline set FAILS strict per-link count criteria (GEH<5% ~6%, corr²
     ~0.76 driven by a few very large stations); it is labelled
     "arterial/screenline-validated, freeway-scope-limited", NOT "validated".
  2. The correlation statistic is labelled corr²/r² (squared PEARSON r), which
     is what it is. The TRUE coefficient of determination R² = 1 - SSE/SST is
     ALSO computed and shown; it is much lower (and can be negative) because it
     penalises the systematic ~-33% under-prediction that corr² is blind to.
  3. MEDIAN signed bias is reported (the mean is outlier-inflated -- a few
     over-predicted small stations pull the mean toward 0). Both are shown.
  4. model=0 stations (real under-predictions where the resident-only model
     assigns no flow to the matched links) are KEPT in every metric. The count
     dropped-if-you-were-to-drop-them is footnoted, and corr² is shown BOTH
     ways (all points vs. sim>0 only) so the effect of dropping is explicit.
  5. Below-1:1 residual captions are stated as HYPOTHESES ("consistent with",
     not "= through passenger cars"); the mechanism is not independently
     confirmed here.

Sim/station = sum over matched link_ids of (linkstats HRS0-24avg x SAMPLE_SCALE),
exactly as validate_base_hybrid.sim_daily_lookup. Observed target = PASSENGER-CAR
AADT 2023 (freight+bus removed via 2023 MDOT vehicle-class shares; facility-median
fallback). The total-AADT set is written to total_aadt/ for completeness.

Bands drawn for reference only (NOT pass gates):
  * GEH=5 (good) / GEH=10 (acceptable) envelopes [FHWA Traffic Analysis Toolbox].
  * per-facility +/-% band [NCHRP 255/765]: freeway +/-7%, principal +/-10%,
    minor +/-15%, collector/local +/-25%.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AADT = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
GEOJSON = ROOT/"data/aadt_2023_bmr_REAL.geojson"
LINKSTATS = ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_speedfix/ITERS/it.64/64.linkstats.txt.gz"
BASEOUT = ROOT/"network_validation_2023/FINAL_FIGURES/aadt_validation_by_route"
BASEOUT.mkdir(parents=True, exist_ok=True)
SAMPLE_SCALE = 10.0

plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":10,"axes.titlesize":12,"axes.labelsize":10.5,
    "legend.fontsize":8.5,"xtick.labelsize":9,"ytick.labelsize":9,
    "axes.linewidth":0.8,"savefig.dpi":300,"figure.dpi":120})
G_GOOD="#7FBF8B"; G_OK="#AEB9C7"; ONEONE="#222222"; PCTLINE="#444444"
C_GREEN="#1B7F3B"; C_AMBER="#E39A11"; C_RED="#C0392B"; C_ZERO="#6C3483"

FAC_PCT={"Interstate/Freeway":0.07,"Principal Arterial":0.10,"Minor Arterial":0.15,"Collector/Local":0.25}

def geh(sim,obs):
    sim=np.asarray(sim,float); obs=np.asarray(obs,float)
    with np.errstate(divide="ignore",invalid="ignore"):
        g=np.sqrt(2*(sim-obs)**2/(sim+obs))
    return np.where((sim+obs)>0,g,np.nan)

def geh_bounds(obs,G):
    """sim bounds at which GEH(sim,obs)=G.  s=[(4o+G^2) +/- G*sqrt(G^2+16o)]/4"""
    obs=np.asarray(obs,float); disc=G*np.sqrt(G*G+16*obs)
    return (4*obs+G*G-disc)/4.0, (4*obs+G*G+disc)/4.0

def metrics(obs,sim,pct_fac):
    """All metrics keep model=0 stations (obs>0). corr2 shown both ways; true R^2
    (1-SSE/SST) computed alongside squared-Pearson corr2; median AND mean bias.
    pct_fac: scalar (route band) or array (per-station band for overall)."""
    obs=np.asarray(obs,float); sim=np.asarray(sim,float); pf=np.asarray(pct_fac,float)
    keep=(obs>0)&np.isfinite(obs)&np.isfinite(sim)          # KEEP sim==0 under-predictions
    obs=obs[keep]; sim=sim[keep]; pf=pf[keep] if pf.ndim else pf
    n=len(obs); n_zero=int((sim==0).sum())
    nan=float("nan")
    if n<2:
        return dict(n=n,n_zero=n_zero,corr2=nan,corr2_nonzero=nan,r2_true=nan,
                    rmse_pct=nan,geh5=nan,geh10=nan,within=nan,meanbias=nan,
                    medbias=nan,medratio=nan)
    # squared Pearson correlation (what the old code MIS-labelled "R^2")
    corr2=float(np.corrcoef(obs,sim)[0,1]**2)
    nz=sim>0
    corr2_nonzero=float(np.corrcoef(obs[nz],sim[nz])[0,1]**2) if nz.sum()>=2 else nan
    # TRUE coefficient of determination about the 1:1 line's data mean
    sse=float(np.sum((sim-obs)**2)); sst=float(np.sum((obs-obs.mean())**2))
    r2_true=float(1.0-sse/sst) if sst>0 else nan
    rmse=np.sqrt(np.mean((sim-obs)**2)); rmse_pct=float(rmse/np.mean(obs)*100)
    g=geh(sim,obs)
    within=float(np.mean(np.abs(sim-obs)/obs<=pf)*100)
    rel=(sim-obs)/obs
    return dict(n=n,n_zero=n_zero,corr2=corr2,corr2_nonzero=corr2_nonzero,r2_true=r2_true,
                rmse_pct=rmse_pct,geh5=float(np.nanmean(g<5)*100),geh10=float(np.nanmean(g<10)*100),
                within=within,meanbias=float(np.mean(rel)*100),medbias=float(np.median(rel)*100),
                medratio=float(np.median(sim/obs)))

def classify(obs,sim,pct_fac):
    obs=np.asarray(obs,float); sim=np.asarray(sim,float); pf=np.asarray(pct_fac,float)
    with np.errstate(divide="ignore",invalid="ignore"):
        inb=np.abs(sim-obs)/obs<=pf
    g=geh(sim,obs)
    zero=sim<=0
    green=inb&~zero; amber=(~inb)&(g<10)&~zero; red=(~inb)&~(g<10)&~zero
    return green,amber,red,zero

def scope_note(facility,m):
    """Honest, criterion-based descriptor. NO fabricated OR-gate PASS."""
    if facility=="Interstate/Freeway":
        return "freeway scope-limited"          # under-predicts through+commercial (excluded)
    if facility=="all":
        return "arterial/screenline-validated; freeway scope-limited"
    return "arterial: weak link-scatter, screenline-checked"

# ---------------------------------------------------------------- linkstats -> sim
print("loading linkstats ...")
ls=pd.read_csv(LINKSTATS,sep="\t",dtype={"LINK":str},low_memory=False)
ls["vol24"]=pd.to_numeric(ls["HRS0-24avg"],errors="coerce")*SAMPLE_SCALE
vol=ls.dropna(subset=["vol24"]).set_index("LINK")["vol24"].to_dict()
def sim_daily(link_ids):
    s=0.0
    for lid in str(link_ids).split(";"):
        lid=lid.strip()
        if lid and lid in vol: s+=vol[lid]
    return s

# ---------------------------------------------------------------- passenger share
gj=json.load(open(GEOJSON))
CLS=["CAR_AADT","LIGHT_TRUCK_AADT","MOTORCYCLE_AADT","SINGLE_UNIT_AADT","COMBINATION_UNIT_AADT","BUS_AADT"]
rows=[]
for f in gj["features"]:
    p=f["properties"]; rec={"LOCATION_ID":p.get("LOCATION_ID")}
    for c in CLS: rec[c]=pd.to_numeric(p.get(c),errors="coerce")
    rows.append(rec)
gc=pd.DataFrame(rows)
gc["cls_sum"]=gc[CLS].sum(axis=1,min_count=1)
gc["pass_sum"]=gc[["CAR_AADT","LIGHT_TRUCK_AADT","MOTORCYCLE_AADT"]].sum(axis=1,min_count=1)
gc["pass_share"]=np.where(gc.cls_sum>0, gc.pass_sum/gc.cls_sum, np.nan)

# ---------------------------------------------------------------- station table
d=pd.read_csv(AADT)
d["sim_AADT"]=d.link_ids.apply(sim_daily)
d=d.merge(gc[["LOCATION_ID","pass_share"]],on="LOCATION_ID",how="left")
facmed=d.groupby("facility").pass_share.median(); globmed=d.pass_share.median()
d["pass_share_used"]=d.pass_share
d.loc[d.pass_share.isna(),"pass_share_used"]=d.loc[d.pass_share.isna(),"facility"].map(facmed).fillna(globmed)
d["obs_total"]=d.obs_AADT
d["obs_pass"]=d.obs_AADT*d.pass_share_used
d["fac_pct"]=d.facility.map(FAC_PCT).fillna(0.15)
d=d[d.obs_total>0].copy()

ROUTES=[
    ("I-95",  (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==95),  "interstate"),
    ("I-695", (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==695), "interstate"),
    ("I-83",  (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==83),  "interstate"),
    ("I-70",  (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==70),  "interstate"),
    ("I-895", (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==895), "interstate"),
    ("MD-295",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==295), "major"),
    ("US-1",  (d.ID_PREFIX=="US")&(d.ID_RTE_NO==1),   "major"),
    ("US-40", (d.ID_PREFIX=="US")&(d.ID_RTE_NO==40),  "major"),
    ("I-97",  (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==97),  "major"),
    ("I-795", (d.ID_PREFIX=="IS")&(d.ID_RTE_NO==795), "major"),
]
ROUTE_FAC={}
for label,mask,kind in ROUTES:
    fac=d[mask].facility.mode()
    ROUTE_FAC[label]=fac.iloc[0] if len(fac) else "Minor Arterial"

CITE=("GEH bands: FHWA Traffic Analysis Toolbox  |  $\\pm$% by facility: NCHRP 255/765  |  "
      "corr$^2$ = squared Pearson r (structure only); R$^2$ = 1$-$SSE/SST (penalises level bias)")
# HYPOTHESES, not confirmed mechanisms (TRB MJ-5)
CAP={
 "I-95":"I-95 (JFK Memorial Hwy). Heavy Northeast-Corridor through traffic. The resident-only model falls "
        "below 1:1; the residual is CONSISTENT WITH un-modeled through/commercial traffic outside scope "
        "(hypothesis; not independently confirmed here).",
 "MD-295":"MD-295 (Baltimore-Washington Pkwy). Major commuter/through corridor; the below-1:1 residual is "
          "consistent with through/non-resident traffic outside a resident-only scope (hypothesis).",
 "I-895":"I-895 (Harbor Tunnel Thruway). Through tunnel bypass; below-1:1 residual is consistent with "
         "through/commercial traffic outside a resident-only model (hypothesis).",
 "I-70":"I-70. Intercity/through corridor; below-1:1 residual is consistent with through traffic outside "
        "resident scope (hypothesis).",
}
def cap_for(label,tag):
    if label in CAP: return CAP[label]
    return ("Green = within the facility $\\pm$% band; amber = GEH<10; red = beyond both; purple = model=0 "
            "(no assigned flow, plotted on the axis). A below-1:1 residual on high-volume roads is "
            "CONSISTENT WITH un-modeled through/commercial traffic (hypothesis, not confirmed here).")

def draw_geh(ax,lo,hi,logx=False):
    gx=np.geomspace(max(lo,1),hi,500) if logx else np.linspace(max(lo,1),hi,500)
    for G,col,al,lab in [(10,G_OK,0.30,"GEH 5-10 (acceptable)"),(5,G_GOOD,0.45,"GEH < 5 (good)")]:
        blo,bhi=geh_bounds(gx,G); blo=np.clip(blo,lo,None)
        ax.fill_between(gx,blo,bhi,color=col,alpha=al,lw=0,zorder=1,label=lab)

def run_set(obs_col,xlabel,outdir,tag):
    outdir.mkdir(parents=True,exist_ok=True); summary=[]
    for label,mask,kind in ROUTES:
        s=d[mask].copy()
        fac=ROUTE_FAC[label]; pct=FAC_PCT.get(fac,0.15)
        obs=s[obs_col].values; sim=s.sim_AADT.values
        m=metrics(obs,sim,pct)
        summary.append(dict(route=label,kind=kind,facility=fac,fac_pct=int(pct*100),
                            scope=scope_note(fac,m),**m))
        keep=(obs>0)&np.isfinite(obs); obs=obs[keep]; sim=sim[keep]
        gr,am,rd,zr=classify(obs,sim,pct)
        hi=max(obs.max(),sim.max())*1.12 if len(obs) else 1e5
        lo=max(1,min(obs.min(),sim.min())*0.7) if len(obs) else 1
        fig,ax=plt.subplots(figsize=(7.6,5.2)); fig.subplots_adjust(left=0.11,right=0.60,top=0.90,bottom=0.17)
        draw_geh(ax,lo,hi)
        ax.plot([lo,hi],[lo,hi],"--",color=ONEONE,lw=1.1,zorder=3,label="1:1 line")
        gg=np.linspace(lo,hi,10)
        ax.plot(gg,gg*(1+pct),":",color=PCTLINE,lw=1.1,zorder=3,label=f"{fac.split('/')[0]} $\\pm${int(pct*100)}% band")
        ax.plot(gg,gg*(1-pct),":",color=PCTLINE,lw=1.1,zorder=3)
        ax.scatter(obs[gr],sim[gr],s=42,c=C_GREEN,edgecolors="k",lw=0.4,alpha=0.9,zorder=6,label=f"within band (n={int(gr.sum())})")
        ax.scatter(obs[am],sim[am],s=42,c=C_AMBER,edgecolors="k",lw=0.4,alpha=0.9,zorder=6,label=f"GEH<10, out of band (n={int(am.sum())})")
        ax.scatter(obs[rd],sim[rd],s=42,c=C_RED,edgecolors="k",lw=0.4,alpha=0.9,zorder=6,label=f"outside both (n={int(rd.sum())})")
        if zr.sum():
            ax.scatter(obs[zr],np.full(int(zr.sum()),lo),s=46,marker="v",c=C_ZERO,edgecolors="k",lw=0.4,
                       alpha=0.9,zorder=7,label=f"model=0 (n={int(zr.sum())})")
        ax.set_xlim(lo,hi); ax.set_ylim(lo,hi); ax.set_aspect("equal","box")
        ax.set_xlabel(xlabel); ax.set_ylabel("Simulated AADT (Base 2023, resident-only)")
        ax.set_title(f"{label} — Simulated vs Observed AADT (Base 2023)")
        ax.legend(loc="upper left",bbox_to_anchor=(1.03,1.0),framealpha=0.75,fontsize=7.2,borderaxespad=0.,edgecolor="0.6")
        txt=(f"n = {m['n']}  (model=0: {m['n_zero']})\n"
             f"corr$^2$ = {m['corr2']:.2f}  (sim>0: {m['corr2_nonzero']:.2f})\n"
             f"true R$^2$ = {m['r2_true']:.2f}\n%RMSE = {m['rmse_pct']:.0f}%\n"
             f"GEH<5 = {m['geh5']:.0f}%   GEH<10 = {m['geh10']:.0f}%\n"
             f"within {int(pct*100)}% band = {m['within']:.0f}%\n"
             f"median bias = {m['medbias']:+.0f}%  (mean {m['meanbias']:+.0f}%)")
        ax.text(1.03,0.30,txt,transform=ax.transAxes,va="top",ha="left",fontsize=8.0,
                bbox=dict(boxstyle="round,pad=0.5",fc="white",ec="0.6",alpha=0.75))
        fig.text(0.02,0.075,cap_for(label,tag),ha="left",va="top",fontsize=7.0,wrap=True,style="italic",color="0.25")
        fig.text(0.02,0.018,CITE,ha="left",va="top",fontsize=6.4,style="italic",color="0.45")
        fig.savefig(outdir/f"aadt_{label.replace('-','').replace(' ','')}.png",bbox_inches="tight",dpi=300)
        plt.close(fig)

    # overall log-log: points colored by OWN facility band; model=0 pinned to axis floor
    ml=d[d.facility.isin(["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"])].copy()
    ml=ml[ml[obs_col]>0]
    mo=metrics(ml[obs_col].values,ml.sim_AADT.values,ml.fac_pct.values)
    fig,ax=plt.subplots(figsize=(8.6,6.0)); fig.subplots_adjust(left=0.10,right=0.64,top=0.92,bottom=0.15)
    obs=ml[obs_col].values; sim=ml.sim_AADT.values
    pos=sim>0
    lo=max(200,min(obs.min(),sim[pos].min())*0.7); hi=max(obs.max(),sim.max())*1.15
    draw_geh(ax,lo,hi,logx=True)
    ax.plot([lo,hi],[lo,hi],"--",color=ONEONE,lw=1.1,zorder=3,label="1:1 line")
    gr,am,rd,zr=classify(obs,sim,ml.fac_pct.values)
    ax.scatter(obs[gr],sim[gr],s=15,c=C_GREEN,alpha=0.6,edgecolors="none",zorder=5,label=f"within own facility band (n={int(gr.sum())})")
    ax.scatter(obs[am],sim[am],s=15,c=C_AMBER,alpha=0.6,edgecolors="none",zorder=5,label=f"GEH<10, out of band (n={int(am.sum())})")
    ax.scatter(obs[rd],sim[rd],s=15,c=C_RED,alpha=0.55,edgecolors="none",zorder=4,label=f"outside both (n={int(rd.sum())})")
    if zr.sum():
        ax.scatter(obs[zr],np.full(int(zr.sum()),lo),s=16,marker="v",c=C_ZERO,alpha=0.7,edgecolors="none",
                   zorder=6,label=f"model=0, on axis (n={int(zr.sum())})")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lo,hi); ax.set_ylim(lo,hi); ax.set_aspect("equal","box")
    ax.set_xlabel(xlabel+" (log)"); ax.set_ylabel("Simulated AADT (Base 2023, resident-only, log)")
    ax.set_title("All count stations (all facilities) — Simulated vs Observed AADT (Base 2023)")
    ax.legend(loc="upper left",bbox_to_anchor=(1.03,1.0),framealpha=0.75,fontsize=7.4,borderaxespad=0.,edgecolor="0.6")
    txt=(f"n = {mo['n']}  (model=0: {mo['n_zero']})\n"
         f"corr$^2$ = {mo['corr2']:.2f}  (sim>0: {mo['corr2_nonzero']:.2f})\n"
         f"true R$^2$ = {mo['r2_true']:.2f}\n%RMSE = {mo['rmse_pct']:.0f}%\n"
         f"GEH<5 = {mo['geh5']:.0f}%   GEH<10 = {mo['geh10']:.0f}%\n"
         f"within facility band = {mo['within']:.0f}%\n"
         f"median bias = {mo['medbias']:+.0f}%  (mean {mo['meanbias']:+.0f}%)")
    ax.text(1.03,0.36,txt,transform=ax.transAxes,va="top",ha="left",fontsize=8.0,
            bbox=dict(boxstyle="round,pad=0.5",fc="white",ec="0.6",alpha=0.75))
    fig.text(0.02,0.085,"Per-facility NCHRP 255/765 reference bands (freeway $\\pm$7% ... collector $\\pm$25%). "
             "corr$^2$ measures STRUCTURE only; the true R$^2$ and median bias expose the systematic "
             "resident-only under-prediction. Below-1:1 residual is consistent with un-modeled "
             "through/commercial traffic (hypothesis).",
             ha="left",va="top",fontsize=6.8,style="italic",color="0.25")
    fig.text(0.02,0.02,CITE,ha="left",va="top",fontsize=6.4,style="italic",color="0.45")
    fig.savefig(outdir/"aadt_ALL_mainline_loglog.png",bbox_inches="tight",dpi=300); plt.close(fig)
    summary.append(dict(route="ALL (mainline)",kind="all",facility="all",fac_pct=-1,
                        scope=scope_note("all",mo),**mo))

    sdf=pd.DataFrame(summary)[["route","facility","fac_pct","n","n_zero","corr2","corr2_nonzero",
                               "r2_true","rmse_pct","geh5","geh10","within","medbias","meanbias",
                               "medratio","scope"]]
    sdf.columns=["route","facility","fac_band_pct","n","n_model0","corr2","corr2_simpos","R2_true",
                 "pctRMSE","GEH_lt5_pct","GEH_lt10_pct","within_facband_pct","median_bias_pct",
                 "mean_bias_pct","median_ratio","scope"]
    sdf=sdf.round({"corr2":3,"corr2_simpos":3,"R2_true":3,"pctRMSE":1,"GEH_lt5_pct":1,
                   "GEH_lt10_pct":1,"within_facband_pct":1,"median_bias_pct":1,"mean_bias_pct":1,
                   "median_ratio":3})
    sdf.to_csv(outdir/"route_validation_summary.csv",index=False)

    # ---- table figure (NO fabricated PASS column) ----
    SCOPE_SHORT={"freeway scope-limited":"fwy scope-ltd",
                 "arterial: weak link-scatter, screenline-checked":"art / screenline",
                 "arterial/screenline-validated; freeway scope-limited":"art+scrn ok; fwy scope-ltd"}
    fig,ax=plt.subplots(figsize=(15.2,4.8)); ax.axis("off")
    cols=["Route","Facility band","n","m=0","corr²","corr²(>0)","R²true","%RMSE",
          "GEH<5","GEH<10","%band","med bias","scope"]
    cell=[]
    for _,r in sdf.iterrows():
        band=f"±{int(r.fac_band_pct)}%" if r.fac_band_pct>=0 else "own"
        cell.append([r.route,(f"{r.facility.split('/')[0]} {band}" if r.facility!='all' else "all"),
                     int(r.n),int(r.n_model0),f"{r.corr2:.2f}",f"{r.corr2_simpos:.2f}",f"{r.R2_true:.2f}",
                     f"{r.pctRMSE:.0f}",f"{r.GEH_lt5_pct:.0f}",f"{r.GEH_lt10_pct:.0f}",
                     f"{r.within_facband_pct:.0f}",f"{r.median_bias_pct:+.0f}",SCOPE_SHORT.get(r.scope,r.scope)])
    t=ax.table(cellText=cell,colLabels=cols,loc="center",cellLoc="center")
    t.auto_set_font_size(False); t.set_fontsize(7.6); t.scale(1,1.5)
    for j in range(len(cols)): t[0,j].set_facecolor("#2E5C8A"); t[0,j].set_text_props(color="white",weight="bold")
    for i in range(1,len(cell)+1):
        scope=cell[i-1][-1]
        shade="#FCEbD5" if "scope-ltd" in scope else "#EAF3EA"   # amber-ish vs green-ish, informational only
        if cell[i-1][1]=="all": shade="#E6ECF3"
        t[i,len(cols)-1].set_facecolor(shade)
        if cell[i-1][1]=="all":
            for j in range(len(cols)): t[i,j].set_facecolor("#E6ECF3")
    ttl=("Per-route validation vs PASSENGER-CAR AADT (freight+bus removed)" if tag=="passenger"
         else "Per-route validation vs TOTAL AADT")
    ax.set_title(ttl+"  —  Base 2023, resident-only  (NO pass/fail gate; each criterion reported honestly)",fontsize=10.5,pad=12)
    fig.text(0.5,0.045,"corr² = squared Pearson r (STRUCTURE only); corr²(>0) drops model=0 stations; "
             "R²true = 1-SSE/SST (penalises the resident-only level deficit). GEH/±%-band shown for reference "
             "(FHWA / NCHRP 255-765) — NOT pass gates.",ha="center",fontsize=6.8,style="italic",color="0.3")
    fig.text(0.5,0.018,"Scope: freeways are SCOPE-LIMITED (resident-only demand excludes through + commercial); "
             "arterials/screenlines validate. This is a documented scope limitation, not \"validated freeways\".",
             ha="center",fontsize=6.9,weight="bold",color="0.15")
    fig.savefig(outdir/"route_validation_summary_table.png",bbox_inches="tight",dpi=300); plt.close(fig)
    print(f"\n=== SUMMARY ({tag}) ==="); print(sdf.to_string(index=False))
    return sdf

sdf_pass=run_set("obs_pass","Observed passenger-car AADT 2023", BASEOUT,"passenger")
sdf_tot =run_set("obs_total","Observed total AADT 2023 (MDOT SHA)", BASEOUT/"total_aadt","total")
print("\nwrote passenger figs ->",BASEOUT,"\n      total figs   ->",BASEOUT/"total_aadt")
