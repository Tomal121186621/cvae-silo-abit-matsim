#!/usr/bin/env python3
"""Hourly validation vs FHWA TMAS 2017 continuous count stations (the 24-h temporal check the AADT
daily comparison can't give — important because congestion pricing is time-of-day).

  1. Observed: average WEEKDAY 24-h bidirectional profile per BMR TMAS station, from the 12 monthly
     MD .VOL files (records are lane-0 directional totals; sum the two directions, average over weekdays).
  2. Match the 35 stations to MATSim links (nearest in-class + anti-parallel = both carriageways).
  3. Modelled: per-link hourly volumes from the baseline events x sampleScale, summed per station.
  4. Compare profile shape (correlation), peak-hour timing, and AM/PM peak magnitude; plot overlays.
"""
import sys, gzip, re, json, collections, math
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from validate_matsim_counts import link_gdf

ROOT=Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
TMAS=ROOT/"data/tmas_2017"; VOL=TMAS/"md_vol"
EVENTS=ROOT/"runs/baseline_5pct/output_events.xml.gz"; SCALE=20.0

def observed_profiles():
    bmr=json.load(open(TMAS/"bmr_tmas_stations.json"))
    prof=collections.defaultdict(lambda: np.zeros(24)); days=collections.defaultdict(set)
    for vf in VOL.glob("*_MD.VOL"):
        for l in open(vf):
            if len(l)<140: continue
            sid=l[5:11]
            if sid not in bmr: continue
            dow=l[19]
            if dow not in "23456": continue  # Mon-Fri (1=Sun..7=Sat)
            try: hrs=np.array([int(l[20+i*5:25+i*5]) for i in range(24)],float)
            except: continue
            prof[sid]+=hrs; days[sid].add((vf.name,l[15:19]))  # unique (month,MMDD)
    out={}
    for sid in prof:
        nd=len(days[sid])
        if nd>=5: out[sid]=prof[sid]/nd   # avg weekday bidirectional 24-h profile
    return bmr, out

def match_stations(bmr):
    import geopandas as gpd
    from shapely.geometry import Point
    g=link_gdf(); gid=dict(zip(g.id,g.geometry)); gux=dict(zip(g.id,g.ux)); guy=dict(zip(g.id,g.uy))
    sidx=g.sindex; gidx=dict(zip(range(len(g)),g.id))
    match={}
    for sid,meta in bmr.items():
        lat=float(meta["lat"])/1e6; lon=-abs(float(str(meta["lon"]).strip())/1e6)
        p=gpd.GeoSeries([Point(lon,lat)],crs="EPSG:4326").to_crs("EPSG:26985").iloc[0]
        cand=[(gidx[i],s.geometry.distance(p) if False else p.distance(gid[gidx[i]])) for i in sidx.query(p.buffer(70),predicate="intersects")]
        cand=[(lid,d) for lid,d in cand if d<=70]
        if not cand: continue
        cand.sort(key=lambda t:t[1]); prim=cand[0][0]; d0=(gux[prim],guy[prim])
        opp=next((lid for lid,d in cand[1:] if gux[lid]*d0[0]+guy[lid]*d0[1]<-0.5),None)
        match[sid]=[prim]+([opp] if opp else [])
    return match

def modelled_hourly(want):
    hourly=collections.defaultdict(lambda: np.zeros(24))
    linkre=re.compile(r'link="([^"]+)"'); timere=re.compile(r'time="([0-9.]+)"')
    with gzip.open(EVENTS,"rt") as f:
        for line in f:
            if "entered link" not in line: continue
            lm=linkre.search(line);
            if not lm or lm.group(1) not in want: continue
            tm=timere.search(line); h=int(float(tm.group(1))//3600)%24
            hourly[lm.group(1)][h]+=SCALE
    return hourly

def main():
    bmr,obs=observed_profiles()
    print(f"TMAS stations with observed weekday profile: {len(obs)}")
    match=match_stations(bmr)
    print(f"matched to network links: {len(match)}")
    want=set(l for ls in match.values() for l in ls)
    mh=modelled_hourly(want)
    rows=[]; mod={}
    for sid in obs:
        if sid not in match: continue
        mp=sum((mh.get(l,np.zeros(24)) for l in match[sid]), np.zeros(24))
        mod[sid]=mp; o=obs[sid]
        if o.sum()==0 or mp.sum()==0: continue
        corr=np.corrcoef(o,mp)[0,1]
        rows.append({"station":sid,"obs_daily":o.sum(),"mod_daily":mp.sum(),"ratio":mp.sum()/o.sum(),
                     "obs_AMpk_h":int(np.argmax(o[6:10])+6),"mod_AMpk_h":int(np.argmax(mp[6:10])+6),
                     "obs_PMpk_h":int(np.argmax(o[15:19])+15),"mod_PMpk_h":int(np.argmax(mp[15:19])+15),
                     "profile_corr":corr})
    res=pd.DataFrame(rows); res.to_csv(ROOT/"validation/tmas_hourly_validation.csv",index=False)
    print(f"\n=== TMAS hourly validation (n={len(res)}) ===")
    print(f"profile shape correlation: median {res.profile_corr.median():.2f} (mean {res.profile_corr.mean():.2f})")
    print(f"daily volume ratio (model/obs): median {res.ratio.median():.2f}")
    print(f"AM-peak hour matched exactly: {100*(res.obs_AMpk_h==res.mod_AMpk_h).mean():.0f}%  (+/-1h: {100*((res.obs_AMpk_h-res.mod_AMpk_h).abs()<=1).mean():.0f}%)")
    print(f"PM-peak hour matched exactly: {100*(res.obs_PMpk_h==res.mod_PMpk_h).mean():.0f}%  (+/-1h: {100*((res.obs_PMpk_h-res.mod_PMpk_h).abs()<=1).mean():.0f}%)")

    # --- plots: aggregate normalized profile + sample stations ---
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    # aggregate (sum over stations), normalized to share-of-day to compare SHAPE
    O=np.sum([obs[s] for s in mod],axis=0); M=np.sum([mod[s] for s in mod],axis=0)
    fig,axes=plt.subplots(1,2,figsize=(16,5.5))
    axes[0].plot(range(24),100*O/O.sum(),"-o",color="#333",label="TMAS observed",ms=4)
    axes[0].plot(range(24),100*M/M.sum(),"-o",color="#C0392B",label="MATSim modelled",ms=4)
    axes[0].set_xlabel("hour"); axes[0].set_ylabel("% of daily traffic"); axes[0].legend()
    axes[0].set_title(f"Aggregate weekday hourly profile shape ({len(mod)} TMAS stations)\ncorr {np.corrcoef(O,M)[0,1]:.3f}")
    axes[0].grid(alpha=0.3)
    # a representative single station
    s=res.sort_values("profile_corr").iloc[len(res)//2].station
    axes[1].plot(range(24),obs[s],"-o",color="#333",label="TMAS observed",ms=4)
    axes[1].plot(range(24),mod[s],"-o",color="#C0392B",label="MATSim modelled",ms=4)
    axes[1].set_xlabel("hour"); axes[1].set_ylabel("vehicles/hour (both dir)"); axes[1].legend()
    axes[1].set_title(f"Station {s} (median-fit)  corr {res[res.station==s].profile_corr.iloc[0]:.2f}")
    axes[1].grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(ROOT/"validation/figures/tmas_hourly_profiles.png",dpi=150,bbox_inches="tight"); plt.close()
    print("wrote validation/tmas_hourly_validation.csv + figures/tmas_hourly_profiles.png")

if __name__=="__main__":
    main()
