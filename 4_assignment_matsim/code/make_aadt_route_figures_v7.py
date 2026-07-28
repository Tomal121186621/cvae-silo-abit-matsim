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
import sys; sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AADT = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
GEOJSON = ROOT/"data/aadt_2023_bmr_REAL.geojson"
LINKSTATS = ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_calibrated/ITERS/it.64/64.linkstats.txt.gz"
# TRB/TRR-styled outputs go in a NEW TRB_figures/ tree; originals under v7_base/ are untouched.
BASEOUT = ROOT/"network_validation_2023/v7_base/TRB_figures/aadt_validation_by_route"
BASEOUT.mkdir(parents=True, exist_ok=True)
SAMPLE_SCALE = 10.0

# shared TRB/TRR rcParams come from trb_style.apply(); reference lines/bands use the shared neutral gray.
G_GOOD="#9A9A9A"; G_OK="#C8C8C8"; ONEONE=trb_style.NEUTRAL; PCTLINE=trb_style.NEUTRAL
# classification categories drawn from the colour-blind-safe Okabe-Ito palette
# (within band / warn / outside / model=0) -- same meaning, same colour everywhere.
C_GREEN="#009E73"; C_AMBER="#E69F00"; C_RED="#D55E00"; C_ZERO=trb_style.NEUTRAL

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
        return "freeway scope-limited"          # under-predicts through / non-resident passenger (hypothesis)
    if facility=="all":
        return "arterial/screenline-checked; freeway scope-limited"
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
# DISCLOSURE (TRB review C): only ~20% of stations (~761 of 3795) carry station-specific vehicle-class
# data (pass_share not-null). The other ~80% get a FACILITY-MEDIAN fallback share (median deduction only
# ~3.4%). So obs_pass is NOT a per-station freight decomposition — it is a class-share adjustment applied
# per-station where measured and by facility-median otherwise. Figures/HEADLINE state this explicitly.
facmed=d.groupby("facility").pass_share.median(); globmed=d.pass_share.median()
d["pass_share_used"]=d.pass_share
d["pass_share_measured"]=d.pass_share.notna()          # True = station-specific class data; False = fallback
d.loc[d.pass_share.isna(),"pass_share_used"]=d.loc[d.pass_share.isna(),"facility"].map(facmed).fillna(globmed)
d["obs_total"]=d.obs_AADT
d["obs_pass"]=d.obs_AADT*d.pass_share_used
print(f"passenger-car adjustment: {int(d.pass_share_measured.sum())} of {len(d)} stations have station-specific "
      f"class data ({d.pass_share_measured.mean()*100:.0f}%); remainder use facility-median fallback "
      f"(median deduction {(1-d.pass_share_used.median())*100:.1f}%).")
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
    # --- major NAMED local / arterial routes (resident-dominated; best-validation expectation) ---
    ("MD-2",  (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==2),   "local"),   # Gov Ritchie Hwy
    ("MD-140",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==140), "local"),   # Reisterstown Rd
    ("MD-45", (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==45),  "local"),   # York Rd
    ("MD-144",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==144), "local"),   # Frederick Rd
    ("MD-26", (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==26),  "local"),   # Liberty Rd
    ("MD-170",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==170), "local"),   # Aviation Blvd
    ("MD-139",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==139), "local"),   # Charles St
    ("MD-25", (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==25),  "local"),   # Falls Rd
    ("MD-648",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==648), "local"),   # Balto-Annapolis Blvd
    ("MD-3",  (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==3),   "local"),   # Crain Hwy
    ("MD-175",(d.ID_PREFIX=="MD")&(d.ID_RTE_NO==175), "local"),   # Annapolis Rd
    ("MD-97", (d.ID_PREFIX=="MD")&(d.ID_RTE_NO==97),  "local"),   # Littlestown Pike
    # --- pooled facility aggregates (all such stations, best resident-scope validation) ---
    ("Minor Arterial (all)",  d.facility=="Minor Arterial",  "aggregate"),
    ("Collector-Local (all)", d.facility=="Collector/Local", "aggregate"),
]
ROUTE_FAC={}
for label,mask,kind in ROUTES:
    fac=d[mask].facility.mode()
    ROUTE_FAC[label]=fac.iloc[0] if len(fac) else "Minor Arterial"

CITE=("GEH<5 bands: FHWA Traffic Analysis Toolbox  |  $\\pm$% facility band (pass metric): NCHRP 255/765")
# HYPOTHESES, not confirmed mechanisms (TRB MJ-5)
CAP={
 "I-95":"I-95 (JFK Memorial Hwy). Heavy Northeast-Corridor through traffic. The resident-only model falls "
        "below 1:1; the residual is CONSISTENT WITH un-modeled through / non-resident passenger traffic outside "
        "scope (freight/bus already removed from the observed target; hypothesis, not independently confirmed here).",
 "MD-295":"MD-295 (Baltimore-Washington Pkwy). Major commuter/through corridor; the below-1:1 residual is "
          "consistent with through / non-resident passenger traffic outside a resident-only scope (hypothesis).",
 "I-895":"I-895 (Harbor Tunnel Thruway). Through tunnel bypass; below-1:1 residual is consistent with "
         "through / non-resident passenger traffic outside a resident-only model (hypothesis, not confirmed here).",
 "I-70":"I-70. Intercity/through corridor; below-1:1 residual is consistent with through / non-resident "
        "passenger traffic outside resident scope (hypothesis).",
}
def cap_for(label,tag):
    if label in CAP: return CAP[label]
    return ("Green = within the facility $\\pm$% band; amber = GEH<10; red = beyond both; purple = model=0 "
            "(no assigned flow, plotted on the axis). A below-1:1 residual on high-volume roads is CONSISTENT "
            "WITH un-modeled through / non-resident passenger traffic (freight/bus already removed; hypothesis, not confirmed here).")

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
        ax.set_xlabel(xlabel); ax.set_ylabel("Simulated AADT (v7 Base 2023, resident-only)")
        ax.set_title(f"{label} — Simulated vs Observed AADT (v7 Base 2023)")
        ax.legend(loc="upper left",bbox_to_anchor=(1.03,1.0),framealpha=0.75,fontsize=7.2,borderaxespad=0.,edgecolor="0.6")
        smalln = m['n']<10; kwin=int(round(m['within']*m['n']/100))
        txt=(f"n = {m['n']}"+("  ‡INDICATIVE" if smalln else "")+"\n"
             f"GEH<5 = {m['geh5']:.0f}%\n"
             f"within $\\pm${int(pct*100)}%: {kwin}/{m['n']} ({m['within']:.0f}%)\n"
             f"median bias = {m['medbias']:+.0f}%")
        ax.text(1.03,0.30,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9.0,
                )
        if smalln:
            ax.text(0.5,0.02,"‡ n < 10 — INDICATIVE ONLY",transform=ax.transAxes,ha="center",va="bottom",
                    fontsize=8.5,color=C_RED)
        fig.text(0.02,0.075,cap_for(label,tag),ha="left",va="top",fontsize=7.0,wrap=True,style="italic",color="0.25")
        fig.text(0.02,0.018,CITE,ha="left",va="top",fontsize=6.4,style="italic",color="0.45")
        stem=f"aadt_{label.replace('-','').replace(' ','')}"
        fig.savefig(outdir/f"{stem}.png",bbox_inches="tight",dpi=300)
        fig.savefig(outdir/f"{stem}.pdf",bbox_inches="tight")
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
    kwin=int(round(mo['within']*mo['n']/100))
    txt=(f"n = {mo['n']}\n"
         f"GEH<5 = {mo['geh5']:.0f}%\n"
         f"within facility band: {kwin}/{mo['n']} ({mo['within']:.0f}%)\n"
         f"median bias = {mo['medbias']:+.0f}%")
    ax.text(1.03,0.34,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9.5)
    fig.text(0.02,0.10,"Per-facility NCHRP 255/765 reference bands (freeway $\\pm$7% ... collector $\\pm$25%); each station scored against its OWN facility band.\n"
             "Observed = passenger-car AADT: freight/bus removed via MDOT 2023 class shares WHERE AVAILABLE (~20% of stations); facility-median\n"
             "fallback (~3.4%) elsewhere (not a per-station decomposition). Below-1:1 residual is consistent with un-modeled through / non-resident\n"
             "passenger traffic outside the resident-only scope (hypothesis, not independently confirmed here).",
             ha="left",va="top",fontsize=6.6,style="italic",color="0.25")
    fig.text(0.02,0.02,CITE,ha="left",va="top",fontsize=6.4,style="italic",color="0.45")
    fig.savefig(outdir/"aadt_ALL_mainline_loglog.png",bbox_inches="tight",dpi=300)
    fig.savefig(outdir/"aadt_ALL_mainline_loglog.pdf",bbox_inches="tight"); plt.close(fig)
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
    # corr²(>0) [model>0 stations] is the PRIMARY structure metric (raw corr² is inflated by model=0
    # clusters, e.g. MD-97 0.64->0.06); † flags n<10 (indicative only).
    SCOPE_SHORT={"freeway scope-limited":"fwy scope-ltd",
                 "arterial: weak link-scatter, screenline-checked":"art / screenline",
                 "arterial/screenline-checked; freeway scope-limited":"art+scrn ok; fwy scope-ltd"}
    cols=["Route","Facility band","n","GEH<5","within ±band","med bias","scope"]
    cell=[]
    for _,r in sdf.iterrows():
        band=f"±{int(r.fac_band_pct)}%" if r.fac_band_pct>=0 else "own"
        flag="‡" if (r.n<10 and r.facility!='all') else ""       # ‡ small-n indicative only
        kwin=int(round(r.within_facband_pct*r.n/100))
        cell.append([f"{r.route}{flag}",(f"{r.facility.split('/')[0]} {band}" if r.facility!='all' else "all"),
                     int(r.n),f"{r.GEH_lt5_pct:.0f}",f"{kwin}/{int(r.n)} ({r.within_facband_pct:.0f}%)",
                     f"{r.median_bias_pct:+.0f}",SCOPE_SHORT.get(r.scope,r.scope)])
    # Layout: dedicated axis band in the MIDDLE; title strictly ABOVE, footnotes strictly BELOW (no overlap).
    nrow=len(cell)
    figh=0.34*nrow+2.6
    fig=plt.figure(figsize=(11.5,figh))
    top_reserve=1.15/figh; bot_reserve=1.25/figh          # inches -> axis fraction reserved for title/footnote
    ax=fig.add_axes([0.02, bot_reserve, 0.96, 1-top_reserve-bot_reserve]); ax.axis("off")
    t=ax.table(cellText=cell,colLabels=cols,cellLoc="center",bbox=[0,0,1,1])
    t.auto_set_font_size(False); t.set_fontsize(7.6)
    for j in range(len(cols)): t[0,j].set_facecolor("#E6E6E6"); t[0,j].set_text_props(color="black")
    for i in range(1,len(cell)+1):
        # subtle neutral shading only to set the pooled 'all' row apart -- no colour coding
        if cell[i-1][1]=="all":
            for j in range(len(cols)): t[i,j].set_facecolor("#F2F2F2")
    obslab=("PASSENGER-CAR AADT (freight+bus removed — HEADLINE)" if tag=="passenger" else "TOTAL AADT (variant)")
    fig.text(0.5, 1-0.55/figh, f"Per-route Simulated vs Observed AADT  —  {obslab}  —  v7 Base 2023, resident-only",
             ha="center",va="center",fontsize=11.5)
    fig.text(0.5, 1-0.92/figh, "Each criterion reported on its own; no pass/fail gate (resident-only scope).",
             ha="center",va="center",fontsize=8.2,style="italic",color="0.2")
    fig.text(0.5, 0.86/figh, "within ±band = stations inside the NCHRP 255/765 facility band (freeway ±7 / principal ±10 / minor ±15 / collector ±25%) — the pass metric.",
             ha="center",va="center",fontsize=6.8,color="0.3")
    fig.text(0.5, 0.46/figh, "GEH<5 is a strict HOURLY threshold shown on DAILY AADT (low shares expected — the ±band + median bias are the daily lens).  ‡ n<10 = indicative only.\n"
             "Passenger-car AADT: freight/bus removed via MDOT 2023 class shares where available (~20% of stations); facility-median fallback (~3.4%) elsewhere (not a per-station decomposition).",
             ha="center",va="center",fontsize=6.6,color="0.15")
    fig.savefig(outdir/"route_validation_summary_table.png",bbox_inches="tight",dpi=300)
    fig.savefig(outdir/"route_validation_summary_table.pdf",bbox_inches="tight"); plt.close(fig)
    print(f"\n=== SUMMARY ({tag}) ==="); print(sdf.to_string(index=False))
    return sdf

sdf_pass=run_set("obs_pass","Observed passenger-car AADT 2023", BASEOUT,"passenger")
sdf_tot =run_set("obs_total","Observed total AADT 2023 (MDOT SHA)", BASEOUT/"total_aadt","total")
print("\nwrote passenger figs ->",BASEOUT,"\n      total figs   ->",BASEOUT/"total_aadt")

# ================================================================ COMBINED POOLED FIGURE
# ONE scatter, ALL non-ramp stations pooled (every facility class), log-log, with a SINGLE
# LARGE uniform +/-50% (0.5x-1.5x) acceptance band applied to ALL roads (NOT the tight
# per-facility NCHRP bands). Points coloured lightly by facility for context only. Neutral
# framing (no pass/fail, no scope verdicts). Same sim (x10) and matching as every other panel.
def combined_all_stations(outpath):
    nr=d[d.facility!="Ramp"].copy()
    obs=nr.obs_pass.values.astype(float); sim=nr.sim_AADT.values.astype(float)
    keep=(obs>0)&np.isfinite(obs)&np.isfinite(sim)
    nr=nr[keep]; obs=obs[keep]; sim=sim[keep]
    n=len(obs); pos=sim>0
    r2=float(np.corrcoef(obs,sim)[0,1]**2)                       # squared Pearson r over all kept stations
    g=geh(sim,obs); geh5=float(np.nanmean(g<5)*100)
    within=(np.abs(sim-obs)/obs<=0.5); kwin=int(within.sum()); wpct=kwin/n*100.0
    FCOL=trb_style.FACILITY_COLORS
    FORD=["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]
    fig,ax=plt.subplots(figsize=(6.8,6.4)); fig.subplots_adjust(left=0.12,right=0.97,top=0.93,bottom=0.16)
    lo=max(200,min(obs.min(),(sim[pos].min() if pos.any() else obs.min()))*0.7)
    hi=max(obs.max(),sim.max())*1.15
    gx=np.array([lo,hi])
    ax.plot([lo,hi],[lo,hi],"-",color=ONEONE,lw=1.1,zorder=3,label="1:1 line")
    ax.plot(gx,1.5*gx,"--",color=PCTLINE,lw=1.2,zorder=2,label="±50% band (0.5×–1.5×)")
    ax.plot(gx,0.5*gx,"--",color=PCTLINE,lw=1.2,zorder=2)
    for f in FORD:
        s=nr[nr.facility==f]; sp=s[s.sim_AADT>0]
        if len(sp):
            ax.scatter(sp.obs_pass,sp.sim_AADT,s=12,c=FCOL[f],alpha=0.45,edgecolors="none",
                       zorder=5,label=f"{f} (n={len(s)})")
    zr=nr[nr.sim_AADT<=0]
    if len(zr):
        ax.scatter(zr.obs_pass,np.full(len(zr),lo),s=13,marker="v",c=C_ZERO,alpha=0.6,
                   edgecolors="none",zorder=6,label=f"Simulated = 0 (no assigned flow), on axis (n={len(zr)})")
    # highlight the I-695 (Baltimore Beltway) count stations with an open circle
    i695=nr[(nr.ID_PREFIX=="IS")&(nr.ID_RTE_NO==695)]; i695p=i695[i695.sim_AADT>0]
    if len(i695p):
        ax.scatter(i695p.obs_pass,i695p.sim_AADT,s=80,facecolors="none",edgecolors="black",
                   linewidths=1.2,zorder=8,label=f"I-695 (Beltway) stations (n={len(i695)})")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lo,hi); ax.set_ylim(lo,hi)
    ax.set_aspect("equal","box")
    ax.set_xlabel("Observed daily traffic [veh/day]")
    ax.set_ylabel("Simulated daily traffic, ×10 [veh/day]")
    ax.set_title("Simulated vs Observed Daily Traffic — Baltimore Region, 2023")
    ax.legend(loc="upper left",framealpha=0.85,fontsize=7.6,edgecolor="0.6")
    txt=(f"n = {n}\nR² = {r2:.2f}\nGEH<5 = {geh5:.0f}%\nwithin ±50%: {kwin}/{n} ({wpct:.0f}%)")
    ax.text(0.97,0.03,txt,transform=ax.transAxes,va="bottom",ha="right",fontsize=9.0)
    fig.text(0.5,0.045,"±50% acceptance band; passenger-car (auto-only) counts; 10% sample scaled ×10.",
             ha="center",va="top",fontsize=7.4,style="italic",color="0.35")
    fig.savefig(f"{outpath}.png",bbox_inches="tight",dpi=300)
    fig.savefig(f"{outpath}.pdf",bbox_inches="tight"); plt.close(fig)
    print(f"\nwrote combined pooled figure -> {outpath}.png/.pdf  "
          f"(n={n}, R²={r2:.3f}, GEH<5={geh5:.1f}%, within±50%={kwin}/{n} ({wpct:.1f}%))")

combined_all_stations(str(BASEOUT.parent/"all_stations_sim_vs_obs"))

# ================================================================ FACILITY-TIER PANELS
# Full FHWA F_SYSTEM hierarchy (raw class, NOT the coarse 4-group). Ramps excluded (not a
# facility class; their station->link snaps are the noisy interchange matches).
FSYS_TIER={1:"Interstate", 2:"Other Freeway-Expressway", 3:"Principal Arterial",
           4:"Minor Arterial", 5:"Major Collector", 6:"Minor Collector-Local", 7:"Minor Collector-Local"}
TIER_ORDER=["Interstate","Other Freeway-Expressway","Principal Arterial",
            "Minor Arterial","Major Collector","Minor Collector-Local"]
TIER_PCT={"Interstate":0.07,"Other Freeway-Expressway":0.07,"Principal Arterial":0.10,
          "Minor Arterial":0.15,"Major Collector":0.20,"Minor Collector-Local":0.25}
TIER_SCOPE={"Interstate":"freeway scope-limited (through / non-resident passenger; hypothesis)",
            "Other Freeway-Expressway":"freeway scope-limited (through / non-resident passenger; hypothesis)",
            "Principal Arterial":"resident-scope arterial",
            "Minor Arterial":"resident-scope arterial",
            "Major Collector":"fine link: some sparse 10%-sample assignment",
            "Minor Collector-Local":"fine link: sparse 10%-sample assignment (model=0 stations)"}
dt=d[d.facility!="Ramp"].copy(); dt["tier"]=dt.F_SYSTEM.map(FSYS_TIER)

def _panel(ax,obs,sim,pct,logscale=False,compact=False):
    obs=np.asarray(obs,float); sim=np.asarray(sim,float)
    keep=(obs>0)&np.isfinite(obs); obs=obs[keep]; sim=sim[keep]
    m=metrics(obs,sim,pct); pos=sim>0
    floor=200 if logscale else 1
    lo=max(floor,min(obs.min(),(sim[pos].min() if pos.any() else obs.min()))*0.7)
    hi=max(obs.max(),sim.max())*1.12
    draw_geh(ax,lo,hi,logx=logscale)
    ax.plot([lo,hi],[lo,hi],"--",color=ONEONE,lw=1.0,zorder=3,label="1:1 line")
    gg=np.geomspace(lo,hi,10) if logscale else np.linspace(lo,hi,10)
    ax.plot(gg,gg*(1+pct),":",color=PCTLINE,lw=1.0,zorder=3,label=f"$\\pm${int(pct*100)}% band")
    ax.plot(gg,gg*(1-pct),":",color=PCTLINE,lw=1.0,zorder=3)
    gr,am,rd,zr=classify(obs,sim,pct); ss=13 if compact else 40; ec="none" if compact else "k"
    ax.scatter(obs[gr],sim[gr],s=ss,c=C_GREEN,edgecolors=ec,lw=0.3,alpha=0.85,zorder=6,label=f"within band (n={int(gr.sum())})")
    ax.scatter(obs[am],sim[am],s=ss,c=C_AMBER,edgecolors=ec,lw=0.3,alpha=0.85,zorder=6,label=f"GEH<10, out of band (n={int(am.sum())})")
    ax.scatter(obs[rd],sim[rd],s=ss,c=C_RED,edgecolors=ec,lw=0.3,alpha=0.8,zorder=5,label=f"outside both (n={int(rd.sum())})")
    if zr.sum():
        ax.scatter(obs[zr],np.full(int(zr.sum()),lo),s=ss,marker="v",c=C_ZERO,edgecolors=ec,lw=0.3,alpha=0.85,zorder=7,label=f"model=0 (n={int(zr.sum())})")
    if logscale: ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo,hi); ax.set_ylim(lo,hi); ax.set_aspect("equal","box")
    return m

def facility_panels(obs_col,xlabel,outdir_ind,combined_path,tag):
    outdir_ind.mkdir(parents=True,exist_ok=True); rows=[]
    hlabel=("passenger-car AADT, HEADLINE" if tag=="passenger" else "TOTAL AADT, variant")
    for tier in TIER_ORDER:
        s=dt[dt.tier==tier]; pct=TIER_PCT[tier]
        fig,ax=plt.subplots(figsize=(7.6,5.2)); fig.subplots_adjust(left=0.11,right=0.60,top=0.90,bottom=0.17)
        m=_panel(ax,s[obs_col].values,s.sim_AADT.values,pct)
        ax.set_xlabel(xlabel+"  [veh/day]"); ax.set_ylabel("Simulated AADT (v7 Base 2023, resident-only)  [veh/day]")
        ax.set_title(f"{tier} (FHWA F_SYSTEM) — Simulated vs Observed AADT, v7 Base 2023")
        ax.legend(loc="upper left",bbox_to_anchor=(1.03,1.0),framealpha=0.75,fontsize=7.2,borderaxespad=0.,edgecolor="0.6")
        kwin=int(round(m['within']*m['n']/100))
        txt=(f"n = {m['n']}\nGEH<5 = {m['geh5']:.0f}%\n"
             f"within $\\pm${int(pct*100)}%: {kwin}/{m['n']} ({m['within']:.0f}%)\n"
             f"median bias = {m['medbias']:+.0f}%")
        ax.text(1.03,0.30,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9.0,
                )
        fig.text(0.02,0.035,f"Observed = {hlabel}.  {TIER_SCOPE[tier]}",ha="left",va="top",fontsize=6.6,style="italic",color="0.25")
        fig.text(0.02,0.008,CITE,ha="left",va="top",fontsize=6.2,style="italic",color="0.45")
        clean=tier.replace(" ","").replace("-","").replace("/","")
        fig.savefig(outdir_ind/f"facility_{clean}.png",bbox_inches="tight",dpi=300)
        fig.savefig(outdir_ind/f"facility_{clean}.pdf",bbox_inches="tight"); plt.close(fig)
        rows.append(dict(level="facility_tier",route=tier,facility=tier,fac_band_pct=int(pct*100),
            n=m["n"],n_model0=m["n_zero"],corr2=round(m["corr2"],3),corr2_simpos=round(m["corr2_nonzero"],3),
            R2_true=round(m["r2_true"],3),pctRMSE=round(m["rmse_pct"],1),GEH_lt5_pct=round(m["geh5"],1),
            GEH_lt10_pct=round(m["geh10"],1),within_facband_pct=round(m["within"],1),
            median_bias_pct=round(m["medbias"],1),mean_bias_pct=round(m["meanbias"],1),
            median_ratio=round(m["medratio"],3),scope=TIER_SCOPE[tier]))
    # combined 2x3 log-log grid (fixed common axes -> the hierarchy gradient reads at a glance)
    if combined_path is not None:
        fig,axs=plt.subplots(2,3,figsize=(15.5,10.4))
        for ax,tier in zip(axs.ravel(),TIER_ORDER):
            s=dt[dt.tier==tier]; pct=TIER_PCT[tier]
            m=_panel(ax,s[obs_col].values,s.sim_AADT.values,pct,logscale=True,compact=True)
            ax.set_title(f"{tier}\nn={m['n']}  GEH<5={m['geh5']:.0f}%  $\\pm${int(pct*100)}%band={m['within']:.0f}%  bias={m['medbias']:+.0f}%",fontsize=8.8)
            ax.set_xlabel("Observed passenger AADT [veh/day, log]"); ax.set_ylabel("Simulated AADT [veh/day, log]")
            ax.legend(fontsize=5.6,loc="upper left",framealpha=0.7,edgecolor="0.7")
        fig.suptitle("v7 Base 2023 — Simulated vs Observed AADT across the FHWA facility hierarchy (resident-only demand, sim $\\times$10; passenger-car AADT)",
                     fontsize=12.5,y=0.995)
        fig.text(0.5,0.95,"Arterials track observed with bias near 0 and high $\\pm$band coverage  ·  freeways under-count (through / non-resident passenger outside resident scope — hypothesis)  ·  "
                 "fine collectors under-assign (sparse 10%-sample).  $\\pm$band = NCHRP facility-band; GEH<5 = strict hourly threshold on daily AADT (low is expected).",
                 ha="center",fontsize=8.2,style="italic",color="0.2")
        fig.tight_layout(rect=[0,0.02,1,0.925])
        fig.text(0.5,0.006,CITE,ha="center",fontsize=7,style="italic",color="0.45")
        fig.savefig(combined_path,bbox_inches="tight",dpi=300)
        fig.savefig(str(Path(combined_path).with_suffix(".pdf")),bbox_inches="tight"); plt.close(fig)
    return pd.DataFrame(rows)

BYFAC=BASEOUT.parent/"by_facility"
tier_pass=facility_panels("obs_pass","Observed passenger-car AADT 2023", BYFAC,
                          BASEOUT.parent/"facility_hierarchy_summary.png","passenger")
tier_tot =facility_panels("obs_total","Observed total AADT 2023 (MDOT SHA)", BYFAC/"total_aadt", None,"total")
tier_pass.to_csv(BYFAC/"facility_tier_summary.csv",index=False)
print("\n=== FACILITY-TIER SUMMARY (passenger) ===")
print(tier_pass[["route","n","n_model0","corr2","GEH_lt5_pct","median_bias_pct","median_ratio","scope"]].to_string(index=False))

# ---- merge tier block + route block into ONE route_validation_summary.csv (level column) ----
rv=pd.read_csv(BASEOUT/"route_validation_summary.csv")
if "level" not in rv.columns: rv.insert(0,"level","route")
cols=list(rv.columns)
tier_block=tier_pass.reindex(columns=cols)
combined=pd.concat([tier_block,rv],ignore_index=True)
combined.to_csv(BASEOUT/"route_validation_summary.csv",index=False)
print("\nwrote facility panels ->",BYFAC,"\n      hierarchy grid ->",BASEOUT.parent/"facility_hierarchy_summary.png",
      "\n      route_validation_summary.csv now carries facility_tier + route blocks")

# ================================================================ SPEED-TIER PANELS
# Hierarchy binned by the matched MATSim link's FREE-FLOW SPEED (freespeed m/s -> mph),
# NOT functional class. Publication quality: 300 dpi PNG + vector PDF, speed band in the
# title, mean/median free-flow speed in the stats box, consistent colour scheme.
import gzip as _gz, re as _re
NETV7=ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_calibrated/output_network.xml.gz"
MS_TO_MPH=2.2369362920544
print("\nparsing freespeed from v7 network ...")
_fs={}; _lre=_re.compile(r'<link id="([^"]+)"[^>]*?freespeed="([^"]+)"')
with _gz.open(NETV7,"rt") as _f:
    for _line in _f:
        _m=_lre.search(_line)
        if _m: _fs[_m.group(1)]=float(_m.group(2))
def _linkspeed_mph(link_ids):
    v=[_fs[l.strip()] for l in str(link_ids).split(";") if l.strip() in _fs]
    return max(v)*MS_TO_MPH if v else np.nan
ds=d[d.facility!="Ramp"].copy()
ds["mph"]=ds.link_ids.apply(_linkspeed_mph)
ds=ds[ds.mph.notna()].copy()

# (name, band-label(mathtext), lo_mph, hi_mph, +/-band). Breakpoints match the freespeed distribution.
SPD_TIERS=[("Freeway","$\\geq$55 mph",55.0,999.0,0.07),
           ("Major Arterial","45$-$55 mph",45.0,55.0,0.10),
           ("Arterial","35$-$45 mph",35.0,45.0,0.15),
           ("Collector","25$-$35 mph",25.0,35.0,0.20),
           ("Local Street","$<$25 mph",0.0,25.0,0.25)]
SPD_SCOPE={"Freeway":"high design-speed: through / non-resident passenger outside resident scope -> under-count (hypothesis)",
           "Major Arterial":"resident-dominated commuter arterial",
           "Arterial":"resident-dominated arterial",
           "Collector":"fine link: some sparse 10%-sample assignment",
           "Local Street":"low design-speed local: sparse 10%-sample assignment (model=0 stations)"}
def save2(fig,stem):
    fig.savefig(f"{stem}.png",bbox_inches="tight",dpi=300)
    fig.savefig(f"{stem}.pdf",bbox_inches="tight")
    plt.close(fig)

def speedtier_panels(obs_col,xlabel,outdir_ind,combined_stem,tag):
    outdir_ind.mkdir(parents=True,exist_ok=True); rows=[]
    hlabel=("passenger-car AADT, HEADLINE" if tag=="passenger" else "TOTAL AADT, variant")
    for name,band,lo_s,hi_s,pct in SPD_TIERS:
        s=ds[(ds.mph>=lo_s)&(ds.mph<hi_s)]
        mspd=float(s.mph.mean()); medspd=float(s.mph.median())
        fig,ax=plt.subplots(figsize=(7.6,5.2)); fig.subplots_adjust(left=0.11,right=0.60,top=0.90,bottom=0.17)
        m=_panel(ax,s[obs_col].values,s.sim_AADT.values,pct)
        ax.set_xlabel(xlabel+"  [veh/day]"); ax.set_ylabel("Simulated AADT (v7 Base 2023, resident-only)  [veh/day]")
        # NOT a speed-accuracy check: stations are BINNED by the road's design/free-flow speed.
        ax.set_title(f"AADT by design speed — {name} ({band})\nSimulated vs Observed, v7 Base 2023 (bins by link free-flow speed; not a speed-accuracy check)",fontsize=10.5)
        ax.legend(loc="upper left",bbox_to_anchor=(1.03,1.0),framealpha=0.9,fontsize=7.4,borderaxespad=0.,edgecolor="0.6")
        kwin=int(round(m['within']*m['n']/100))
        txt=(f"mean design speed = {mspd:.0f} mph\n"
             f"n = {m['n']}\nGEH<5 = {m['geh5']:.0f}%\n"
             f"within $\\pm${int(pct*100)}%: {kwin}/{m['n']} ({m['within']:.0f}%)\n"
             f"median bias = {m['medbias']:+.0f}%")
        ax.text(1.03,0.32,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9.0)
        fig.text(0.02,0.035,f"Observed = {hlabel}.  {SPD_SCOPE[name]}",ha="left",va="top",fontsize=6.8,style="italic",color="0.25")
        fig.text(0.02,0.008,CITE,ha="left",va="top",fontsize=6.2,style="italic",color="0.45")
        clean=name.replace(" ","")
        save2(fig,str(outdir_ind/f"speedtier_{clean}"))
        rows.append(dict(level="speed_tier",route=name,speed_band=band.replace("$","").replace("\\geq","≥").replace("\\","").replace("geq","≥"),
            mean_mph=round(mspd,1),median_mph=round(medspd,1),facility=name,fac_band_pct=int(pct*100),
            n=m["n"],n_model0=m["n_zero"],corr2=round(m["corr2"],3),corr2_simpos=round(m["corr2_nonzero"],3),
            R2_true=round(m["r2_true"],3),pctRMSE=round(m["rmse_pct"],1),GEH_lt5_pct=round(m["geh5"],1),
            GEH_lt10_pct=round(m["geh10"],1),within_facband_pct=round(m["within"],1),
            median_bias_pct=round(m["medbias"],1),mean_bias_pct=round(m["meanbias"],1),
            median_ratio=round(m["medratio"],3),scope=SPD_SCOPE[name]))
    # combined grid (log-log common axes) -> design-speed gradient at a glance. 5 tiers -> the 6th cell
    # is a STATS/legend cell (no empty white subplot).
    if combined_stem is not None:
        fig,axs=plt.subplots(2,3,figsize=(15.5,10.4)); axl=axs.ravel()
        statlines=[]
        for ax,(name,band,lo_s,hi_s,pct) in zip(axl,SPD_TIERS):
            s=ds[(ds.mph>=lo_s)&(ds.mph<hi_s)]; mspd=float(s.mph.mean())
            m=_panel(ax,s[obs_col].values,s.sim_AADT.values,pct,logscale=True,compact=True)
            ax.set_title(f"{name} ({band}); mean {mspd:.0f} mph\nn={m['n']}  GEH<5={m['geh5']:.0f}%  $\\pm${int(pct*100)}%band={m['within']:.0f}%  bias={m['medbias']:+.0f}%",fontsize=8.5)
            ax.set_xlabel("Observed AADT [veh/day, log]"); ax.set_ylabel("Simulated AADT [veh/day, log]")
            ax.legend(fontsize=5.6,loc="upper left",framealpha=0.8,edgecolor="0.7")
            statlines.append(f"{name:14s} {band:9s} mean {mspd:>3.0f}mph  n={m['n']:>4d}  GEH<5={m['geh5']:>3.0f}%  "
                             f"±band={m['within']:>4.0f}%  bias={m['medbias']:>+4.0f}%")
        cax=axl[-1]; cax.axis("off")   # 6th cell -> stats summary (not blank)
        cax.text(0.0,0.98,"Summary (design-speed tiers)",transform=cax.transAxes,va="top",ha="left",
                 fontsize=10)
        cax.text(0.0,0.86,"\n".join(statlines),transform=cax.transAxes,va="top",ha="left",fontsize=7.4,family="monospace")
        cax.text(0.0,0.30,"$\\pm$band = NCHRP facility-band pass rate; median bias = daily lens.\n"
                 "GEH<5 = strict HOURLY threshold on DAILY AADT — low is\nEXPECTED. Bins are by the road's DESIGN "
                 "(free-flow) speed;\nthis is NOT a speed-accuracy check.",
                 transform=cax.transAxes,va="top",ha="left",fontsize=7.2,style="italic",color="0.2")
        fig.suptitle("v7 Base 2023 — AADT by DESIGN (free-flow) SPEED tier (resident-only demand, sim $\\times$10; HEADLINE = passenger-car AADT)",
                     fontsize=12.5,y=0.995)
        fig.text(0.5,0.95,"High design-speed freeways under-count (through / non-resident passenger outside resident scope; hypothesis)  $\\rightarrow$  "
                 "mid-speed resident arterials track observed near zero bias  $\\rightarrow$  low-speed local streets sparse "
                 "(10%-sample zero-assignment).",ha="center",fontsize=8.2,style="italic",color="0.2")
        fig.tight_layout(rect=[0,0.02,1,0.925])
        fig.text(0.5,0.006,CITE,ha="center",fontsize=7,style="italic",color="0.45")
        save2(fig,combined_stem)
    return pd.DataFrame(rows)

BYSPD=BASEOUT.parent/"by_speedtier"
spd_pass=speedtier_panels("obs_pass","Observed passenger-car AADT 2023", BYSPD,
                          str(BASEOUT.parent/"speedtier_hierarchy_summary"),"passenger")
spd_tot =speedtier_panels("obs_total","Observed total AADT 2023 (MDOT SHA)", BYSPD/"total_aadt", None,"total")
spd_pass.to_csv(BYSPD/"speedtier_summary.csv",index=False)
print("\n=== SPEED-TIER SUMMARY (passenger) ===")
print(spd_pass[["route","speed_band","mean_mph","n","n_model0","corr2","GEH_lt5_pct","median_bias_pct","median_ratio"]].to_string(index=False))

# merge speed-tier block into route_validation_summary.csv (level column already present)
rv2=pd.read_csv(BASEOUT/"route_validation_summary.csv")
spd_block=spd_pass.reindex(columns=[c for c in rv2.columns])
# carry the speed-only extra cols too (speed_band/mean_mph/median_mph) by unioning columns
allcols=list(dict.fromkeys(list(rv2.columns)+["speed_band","mean_mph","median_mph"]))
rv2=rv2.reindex(columns=allcols); spd_full=spd_pass.reindex(columns=allcols)
pd.concat([spd_full,rv2],ignore_index=True).to_csv(BASEOUT/"route_validation_summary.csv",index=False)
print("\nwrote speed-tier panels ->",BYSPD," (PNG 300dpi + PDF)",
      "\n      speed hierarchy grid ->",str(BASEOUT.parent/"speedtier_hierarchy_summary")+".{png,pdf}",
      "\n      route_validation_summary.csv now carries speed_tier + facility_tier + route blocks")
