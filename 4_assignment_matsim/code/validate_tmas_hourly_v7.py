#!/usr/bin/env python3
"""v7 Base 2023 — TEMPORAL (time-of-day) validation vs FHWA TMAS 2023 continuous-count HOURLY data.

Complements the daily-AADT check with a 24-hour SHAPE comparison. The key question is not the
absolute freeway LEVEL (the resident-only demand under-counts through + commercial traffic) but
whether the simulated TIME-OF-DAY PATTERN is right: peaks at the correct hours, correct peaking
intensity (K-factor), correct 24h profile shape.

OBSERVED (engine-independent):
  Average-WEEKDAY 24-h volume profile per TMAS continuous station, built from the 12 monthly MD .VOL
  files (`data/tmas_2023/md_vol/MD_*_2023 (TMAS).VOL`, pipe-delimited, one row per station/dir/lane/
  date with hour_00..hour_23). Aggregation, exactly:
    1. keep weekday records only (day_of_week in {2,3,4,5,6} = Mon-Fri; TMAS 1=Sun..7=Sat),
    2. for each (station, date) SUM over travel_dir + travel_lane -> station daily 24h vector (both
       directions, all lanes = what a matched anti-parallel MATSim link pair carries),
    3. MEAN that daily vector over all weekday dates across all 12 months -> avg-weekday profile.

SIMULATED (v7 base):
  Per-link hourly volumes HRS{h}-{h+1}avg from the it.64 linkstats of the v7 base run
  `scenarios/02_i695_congestion_pricing/output_base/base_calibrated/ITERS/it.64/64.linkstats.txt.gz`,
  scaled x10 (10% population sample). Summed over the matched link pair (both carriageways).

MATCHING:
  TMAS continuous stations are NOT in the AADT short-count match audit (that file keys on S-prefixed
  short-count IDs), so we reuse the spatial station->link matching already computed for these 29 TMAS
  stations in network_validation_2023/tmas/tmas_validation_2023.csv (nearest in-functional-class link
  + its anti-parallel twin; matching is on network GEOMETRY, identical across scenarios). All matched
  link ids are present in the v7 linkstats.

SPEED TIER:
  From the matched link's free-flow speed in the v7 output network (max freespeed of the pair, m/s
  -> mph), using the same breakpoints as the AADT speed-tier work
  (Freeway >=55 / Major Arterial 45-55 / Arterial 35-45 / Collector 25-35 / Local Street <25 mph).

METRICS per station (+ aggregated per tier):
  AM & PM peak-hour TIMING (obs vs sim), peak-hour factor / K-factor = peak-hour vol / daily
  (obs vs sim), SHAPE correlation of the 24 hourly SHARES (level normalised out so the freeway
  level under-count doesn't dominate), hourly GEH at the peak hour, and daily sim/obs for context.

Writes network_validation_2023/v7_base/tmas_hourly/{figures, tmas_hourly_summary.csv}.
"""
import glob, gzip, re
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys; sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
VOLGLOB = str(ROOT/"data/tmas_2023/md_vol/*.VOL")
STA     = ROOT/"data/tmas_2023/MD_2023 (TMAS).STA"
MATCH   = ROOT/"network_validation_2023/tmas/tmas_validation_2023.csv"   # reuse station->link matching
V7BASE  = ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_calibrated"
LINKSTATS = V7BASE/"ITERS/it.64/64.linkstats.txt.gz"
NET       = V7BASE/"output_network.xml.gz"
OUT     = ROOT/"network_validation_2023/v7_base/tmas_hourly"
FIGDIR  = OUT/"TRB_figures"   # TRB/TRR-styled figures; original figures/ untouched
SCALE   = 10.0                       # 10% sample -> x10
MS_TO_MPH = 2.2369362920544
HRS = [f"hour_{h:02d}" for h in range(24)]
WEEKDAYS = {"2","3","4","5","6"}     # Mon-Fri (TMAS 1=Sun..7=Sat)

# ---- speed-tier scheme (matches make_aadt_route_figures_v7.py SPD_TIERS) --------
def tier_of(mph):
    if not np.isfinite(mph): return "Unmatched"
    if mph >= 55: return "Freeway"
    if mph >= 45: return "Major Arterial"
    if mph >= 35: return "Arterial"
    if mph >= 25: return "Collector"
    return "Local Street"
TIER_ORDER = ["Freeway","Major Arterial","Arterial","Collector","Local Street"]
TIER_BAND  = {"Freeway":"≥55 mph","Major Arterial":"45–55 mph","Arterial":"35–45 mph",
              "Collector":"25–35 mph","Local Street":"<25 mph"}
TIER_COL   = {"Freeway":trb_style.PALETTE[0],"Major Arterial":trb_style.PALETTE[2],
              "Arterial":trb_style.PALETTE[3],"Collector":trb_style.PALETTE[4],
              "Local Street":trb_style.PALETTE[5]}

def geh(m, o):
    m=float(m); o=float(o)
    return np.sqrt(2*(m-o)**2/(m+o)) if (m+o)>0 else np.nan

# ---------------------------------------------------------------- observed .VOL
def observed_profiles():
    frames=[]
    for f in sorted(glob.glob(VOLGLOB)):
        v=pd.read_csv(f, sep="|", dtype=str)
        v=v[v.day_of_week.isin(WEEKDAYS)]
        for h in HRS: v[h]=pd.to_numeric(v[h], errors="coerce").fillna(0.0)
        frames.append(v[["station_id","month_record","day_record"]+HRS])
    vol=pd.concat(frames, ignore_index=True)
    daily=vol.groupby(["station_id","month_record","day_record"], as_index=False)[HRS].sum()  # sum dir+lane
    prof=daily.groupby("station_id", as_index=False)[HRS].mean()                              # avg weekday
    ndays=daily.groupby("station_id").size().rename("ndays")
    prof=prof.merge(ndays, on="station_id")
    return prof

# ---------------------------------------------------------------- v7 linkstats + freespeed
def link_hourly_and_speed():
    df=pd.read_csv(LINKSTATS, sep="\t", dtype={"LINK":str}, low_memory=False)
    hr=np.array([df[f"HRS{h}-{h+1}avg"].astype(float).values for h in range(24)]).T * SCALE  # (nlink,24)
    hourly=dict(zip(df.LINK, hr))
    fs={}; lre=re.compile(r'<link id="([^"]+)"[^>]*?freespeed="([^"]+)"')
    with gzip.open(NET,"rt") as fh:
        for line in fh:
            m=lre.search(line)
            if m: fs[m.group(1)]=float(m.group(2))
    return hourly, fs

def main():
    FIGDIR.mkdir(parents=True, exist_ok=True)
    obs=observed_profiles()
    match=pd.read_csv(MATCH, dtype={"station_id":str})
    hourly, fs = link_hourly_and_speed()

    rows=[]; prof={}
    for _,mrow in match.iterrows():
        sid=mrow.station_id
        orow=obs[obs.station_id==sid]
        if orow.empty: continue
        o=orow[HRS].values.astype(float)[0]
        links=[l.strip() for l in str(mrow.link_ids).split(";") if l.strip()]
        m=np.sum([hourly[l] for l in links if l in hourly], axis=0)
        if np.ndim(m)==0: m=np.zeros(24)
        mph=max([fs[l]*MS_TO_MPH for l in links if l in fs], default=np.nan)
        tier=tier_of(mph)
        od=o.sum(); md=m.sum()
        # peak-hour timing (search AM 6-9, PM 15-18 windows)
        o_am=6+int(np.argmax(o[6:10])); o_pm=15+int(np.argmax(o[15:19]))
        m_am=6+int(np.argmax(m[6:10])) if m.sum()>0 else -1
        m_pm=15+int(np.argmax(m[15:19])) if m.sum()>0 else -1
        # K-factor / peak-hour factor = single highest hour / daily
        o_pk=int(np.argmax(o)); m_pk=int(np.argmax(m)) if m.sum()>0 else -1
        o_K=o[o_pk]/od if od>0 else np.nan
        m_K=m[m_pk]/md if md>0 else np.nan
        # shape correlation on hourly SHARES (level normalised out)
        os_=o/od if od>0 else o; ms_=m/md if md>0 else m
        corr=np.corrcoef(os_,ms_)[0,1] if (os_.std()>0 and ms_.std()>0) else np.nan
        # hourly GEH at the observed peak hour
        gpk=geh(m[o_pk], o[o_pk])
        rows.append(dict(station=sid, route=int(mrow.route), road=str(mrow.location).strip(),
            tier=tier, freeflow_mph=round(mph,1), n_links=len(links),
            obs_daily=round(od), sim_daily=round(md), daily_ratio=round(md/od,3) if od>0 else np.nan,
            obs_AM_peak_hr=o_am, sim_AM_peak_hr=m_am, obs_PM_peak_hr=o_pm, sim_PM_peak_hr=m_pm,
            obs_peak_hr=o_pk, sim_peak_hr=m_pk,
            obs_PHF_Kfac=round(o_K,4), sim_PHF_Kfac=round(m_K,4),
            shape_corr=round(corr,4), peak_hour_GEH=round(gpk,1)))
        prof[sid]=(o,m,tier,mph)
    res=pd.DataFrame(rows)
    res["tier"]=pd.Categorical(res.tier, TIER_ORDER+["Unmatched"], ordered=True)
    res=res.sort_values(["tier","route","station"]).reset_index(drop=True)

    # ------- station selection: 2-3 best-matched per tier + all I-695 + all I-95
    sel=set()
    for t in TIER_ORDER:
        sub=res[(res.tier==t)&(res.sim_daily>0)]
        sub=sub.sort_values("shape_corr", ascending=False)
        for s in sub.station.head(3): sel.add(s)
    corridor={"I-695":sorted(res[(res.route==695)&res.road.str.startswith("IS")].station),
              "I-95":sorted(res[res.route==95].station)}
    for lst in corridor.values(): sel.update(lst)
    res["selected"]=res.station.isin(sel)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT/"tmas_hourly_summary.csv", index=False)

    # ============================================================ FIGURES
    def panel(ax, sid):
        o,m,t,mph=prof[sid]
        r=res[res.station==sid].iloc[0]
        ax.plot(range(24), o, "-o", color=trb_style.OBS, ms=3.2, lw=1.6, label="TMAS observed")
        ax.plot(range(24), m, "-s", color=trb_style.SIM, ms=3.0, lw=1.6, label="MATSim sim ×10")
        ax.axvspan(6,9,color=trb_style.NEUTRAL,alpha=0.05); ax.axvspan(15,18,color=trb_style.NEUTRAL,alpha=0.05)
        ax.set_xlim(0,23); ax.set_xticks([0,6,12,18,23]); ax.grid(alpha=0.25,lw=0.5)
        ax.set_title(f"{sid}  ·  {r.road[:34]}", fontsize=8.2, loc="left")
        ax.text(0.98,0.94,f"{t} ({mph:.0f} mph)\nshape r={r.shape_corr:.2f}   sim/obs={r.daily_ratio:.2f}\n"
                f"peak hr {int(r.obs_peak_hr)}/{int(r.sim_peak_hr)} (obs/sim)",
                transform=ax.transAxes, va="top", ha="right", fontsize=6.6)

    fignum=[0]
    def grid_fig(sids, title, stem, ncol=3):
        if not sids: return
        n=len(sids); nr=int(np.ceil(n/ncol))
        fig,axs=plt.subplots(nr,ncol,figsize=(4.7*ncol,3.3*nr),squeeze=False)
        for ax,sid in zip(axs.ravel(), sids): panel(ax, sid)
        for ax in axs.ravel()[n:]: ax.axis("off")
        axs.ravel()[0].legend(fontsize=6.8, loc="upper left", framealpha=0.85)
        for ax in axs[-1,:]: ax.set_xlabel("hour of day", fontsize=8)
        for ax in axs[:,0]:  ax.set_ylabel("veh/hr (both dir)", fontsize=8)
        fig.suptitle(title, fontsize=11, y=0.997, fontweight="normal")
        fignum[0]+=1
        fig.text(0.5,0.005,f"Figure {fignum[0]}. {title}. Simulated v7 Base 2023 (resident-only demand, "
                 "sim ×10) vs FHWA TMAS 2023 avg-weekday hourly profile. Shaded = AM/PM peak windows; "
                 "shape r on hourly shares (level normalised out).",
                 ha="center", fontsize=7.6, color="0.15", wrap=True)
        fig.tight_layout(rect=[0,0.02,1,0.975])
        fig.savefig(f"{stem}.png", dpi=300, bbox_inches="tight")
        fig.savefig(f"{stem}.pdf", bbox_inches="tight"); plt.close(fig)

    # per-tier small multiples (selected stations)
    for t in TIER_ORDER:
        sids=res[(res.tier==t)&(res.selected)].station.tolist()
        grid_fig(sids, f"TMAS hourly profile — {t} tier ({TIER_BAND[t]})",
                 str(FIGDIR/f"tmas_hourly_{t.replace(' ','')}"))
    # corridor figures: I-695 and I-95 (all matched stations on each)
    grid_fig(corridor["I-695"], "TMAS hourly profile — I-695 Baltimore Beltway (all continuous stations)",
             str(FIGDIR/"tmas_hourly_I695"))
    grid_fig(corridor["I-95"],  "TMAS hourly profile — I-95 corridor (all continuous stations)",
             str(FIGDIR/"tmas_hourly_I95"))

    # normalised AGGREGATE shape overlay + per-tier mean shape
    fig,axs=plt.subplots(1,2,figsize=(15,5.3))
    O=np.sum([prof[s][0] for s in prof],axis=0); M=np.sum([prof[s][1] for s in prof],axis=0)
    axs[0].plot(range(24),100*O/O.sum(),"-o",color=trb_style.OBS,ms=4,label="TMAS observed")
    axs[0].plot(range(24),100*M/M.sum(),"-s",color=trb_style.SIM,ms=4,label="MATSim sim ×10")
    axs[0].axvspan(6,9,color=trb_style.NEUTRAL,alpha=0.06); axs[0].axvspan(15,18,color=trb_style.NEUTRAL,alpha=0.06)
    axs[0].set_title(f"Aggregate weekday profile SHAPE ({len(prof)} stations)\nshape r={np.corrcoef(O/O.sum(),M/M.sum())[0,1]:.3f}")
    axs[0].set_xlabel("hour"); axs[0].set_ylabel("% of daily traffic"); axs[0].legend(); axs[0].grid(alpha=0.25)
    for t in TIER_ORDER:
        sids=[s for s in prof if prof[s][2]==t]
        if not sids: continue
        Ot=np.sum([prof[s][0] for s in sids],axis=0)
        axs[1].plot(range(24),100*Ot/Ot.sum(),"-o",ms=3,color=TIER_COL[t],label=f"{t} obs (n={len(sids)})")
        Mt=np.sum([prof[s][1] for s in sids],axis=0)
        if Mt.sum()>0: axs[1].plot(range(24),100*Mt/Mt.sum(),"--s",ms=2.5,color=TIER_COL[t],alpha=0.7)
    axs[1].set_title("Per-tier mean shape — obs (solid) vs sim ×10 (dashed)")
    axs[1].set_xlabel("hour"); axs[1].set_ylabel("% of daily traffic"); axs[1].legend(fontsize=7); axs[1].grid(alpha=0.25)
    fignum[0]+=1
    fig.text(0.5,0.005,f"Figure {fignum[0]}. Aggregate and per-tier weekday time-of-day profile shape, "
             "simulated v7 Base 2023 (×10) vs FHWA TMAS 2023 observed.",
             ha="center", fontsize=7.8, color="0.15", wrap=True)
    fig.tight_layout(rect=[0,0.03,1,1]); fig.savefig(FIGDIR/"tmas_hourly_aggregate_shape.png",dpi=300,bbox_inches="tight")
    fig.savefig(FIGDIR/"tmas_hourly_aggregate_shape.pdf",bbox_inches="tight"); plt.close(fig)

    # ============================================================ CONSOLE REPORT
    def match_pct(a,b,tol=0):
        d=(res[a]-res[b]).abs(); return 100*(d<=tol).mean()
    print(f"\n=== v7 Base TMAS 2023 HOURLY (temporal) validation — {len(res)} stations ===")
    print(f"stations by tier: "+", ".join(f"{t}={int((res.tier==t).sum())}" for t in TIER_ORDER))
    print(f"AM peak hour exact match {match_pct('obs_AM_peak_hr','sim_AM_peak_hr'):.0f}%  (±1h {match_pct('obs_AM_peak_hr','sim_AM_peak_hr',1):.0f}%)")
    print(f"PM peak hour exact match {match_pct('obs_PM_peak_hr','sim_PM_peak_hr'):.0f}%  (±1h {match_pct('obs_PM_peak_hr','sim_PM_peak_hr',1):.0f}%)")
    print(f"shape correlation: median {res.shape_corr.median():.3f}  mean {res.shape_corr.mean():.3f}")
    print(f"K-factor (peak/daily): obs median {res.obs_PHF_Kfac.median():.3f}  sim median {res.sim_PHF_Kfac.median():.3f}")
    print(f"daily sim/obs: median {res.daily_ratio.median():.2f}  (LEVEL under-count expected on freeways)")
    print("\nPER-TIER:")
    agg=res.groupby("tier",observed=True).agg(n=("station","size"),
        shape_r=("shape_corr","median"), obs_K=("obs_PHF_Kfac","median"), sim_K=("sim_PHF_Kfac","median"),
        pk_GEH=("peak_hour_GEH","median"), daily_ratio=("daily_ratio","median")).round(3)
    print(agg.to_string())
    print("\nSELECTED STATIONS (plotted):")
    cols=["station","route","tier","freeflow_mph","obs_AM_peak_hr","sim_AM_peak_hr","obs_PM_peak_hr",
          "sim_PM_peak_hr","obs_PHF_Kfac","sim_PHF_Kfac","shape_corr","peak_hour_GEH","daily_ratio"]
    print(res[res.selected][cols].to_string(index=False))
    print(f"\nI-695 stations: {corridor['I-695']}\nI-95 stations:  {corridor['I-95']}")
    print(f"\nwrote {OUT/'tmas_hourly_summary.csv'} + {FIGDIR}/*.png/.pdf")

if __name__=="__main__":
    main()
