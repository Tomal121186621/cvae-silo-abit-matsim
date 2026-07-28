#!/usr/bin/env python3
"""Daily validation: MATSim it.64 link volumes (x10) vs MDOT SHA AADT 2023 (real).

Spatially match each AADT point to the nearest LOADED in-class car carriageway pair
(both directions), compare model daily volume to AADT_2023, and report GEH / R2 / bias
overall and by FHWA facility class. Writes aadt/aadt_validation_2023.csv.
"""
import math
import numpy as np, pandas as pd
import geopandas as gpd
from netval2023_common import (ROOT, OUTDIR, CRS, link_gdf, geh,
                               FSYS_GROUP, GROUP_ORDER, FSYS_HWY, FSYS_TOL)

AADT_FILE = ROOT/"data/aadt_2023_bmr_REAL.geojson"

def match_stations(g):
    """Snap each AADT point to primary + opposing loaded in-class car link. Returns DataFrame."""
    aadt=gpd.read_file(AADT_FILE).to_crs(CRS)
    aadt=aadt[aadt.AADT_2023>0].copy()
    gid=dict(zip(g.id,g.geometry)); ghwy=dict(zip(g.id,g.hwy))
    gux=dict(zip(g.id,g.ux)); guy=dict(zip(g.id,g.uy)); gvol=dict(zip(g.id,g.vol24))
    gidx={i:lid for i,lid in enumerate(g.id)}
    sidx=g.sindex
    rows=[]
    for _,s in aadt.iterrows():
        fs=int(s.F_SYSTEM) if pd.notna(s.F_SYSTEM) else 4
        tol=FSYS_TOL.get(fs,45.0)
        if s.ID_PREFIX=="RP": tol=min(tol,45.0)   # ramp counts: tighter
        allowed=FSYS_HWY.get(fs, None)
        cand=list(sidx.query(s.geometry.buffer(tol), predicate="intersects"))
        inclass=[]   # (lid, dist)
        for idx in cand:
            lid=gidx[idx]; hw=ghwy[lid]
            if allowed is not None and hw not in allowed: continue
            d=s.geometry.distance(gid[lid])
            if d<=tol: inclass.append((lid,d))
        geom_match = len(inclass)>0
        if not inclass:  # fallback: nearest car link (any class) within 45 m
            near=[(gidx[idx], s.geometry.distance(gid[gidx[idx]])) for idx in cand]
            near=[(lid,d) for lid,d in near if d<=45]
            inclass=near
        loaded=[(lid,d) for lid,d in inclass if gvol[lid]>0]
        if loaded:
            # primary = nearest loaded in-class link
            loaded.sort(key=lambda t:t[1])
            prim,pd0=loaded[0]; ux,uy=gux[prim],guy[prim]
            # opposing carriageway = nearest anti-parallel loaded in-class link
            opp=[(lid,d) for lid,d in loaded if lid!=prim and gux[lid]*ux+guy[lid]*uy<-0.3]
            opp.sort(key=lambda t:t[1])
            chosen=[prim]+([opp[0][0]] if opp else [])
            model=sum(gvol[l] for l in chosen)
            mindist=pd0; nlk=len(chosen)
            hwys=";".join(sorted(set(ghwy[l] for l in chosen)))
        else:
            model=0.0; mindist=(inclass[0][1] if inclass else np.nan); nlk=0; hwys=""
            chosen=[]
        fac = "Ramp" if s.ID_PREFIX=="RP" else FSYS_GROUP.get(fs,"Other")
        rows.append({"LOCATION_ID":s.LOCATION_ID,"COUNTY_DESC":s.COUNTY_DESC,
                     "ID_PREFIX":s.ID_PREFIX,"ID_RTE_NO":s.ID_RTE_NO,"ROADNAME":s.ROADNAME,
                     "F_SYSTEM":fs,"facility":fac,
                     "obs_AADT":float(s.AADT_2023),"obs_AAWDT":float(s.AAWDT_2023) if pd.notna(s.AAWDT_2023) else np.nan,
                     "model_daily":model,"link_ids":";".join(chosen),"n_links":nlk,
                     "hwy":hwys,"min_dist":mindist,"geom_match":int(geom_match),
                     "lon":s.geometry.x,"lat":s.geometry.y})
    return pd.DataFrame(rows), len(aadt)

def summarize(df, label):
    ok=df[df.model_daily>0].copy()
    if len(ok)==0: return None
    g=geh(ok.model_daily.values, ok.obs_AADT.values)
    m=ok.model_daily.values; o=ok.obs_AADT.values
    # R2 of model vs obs (about 1:1? report coeff of determination against 45-deg and regression slope)
    slope=np.polyfit(o,m,1)[0]
    ss_res=np.sum((m-o)**2); ss_tot=np.sum((o-o.mean())**2)
    r2=1-ss_res/ss_tot if ss_tot>0 else np.nan
    corr=np.corrcoef(o,m)[0,1]
    return {"label":label,"n":len(ok),
            "pctGEH5":100*np.mean(g<5),"pctGEH10":100*np.mean(g<10),
            "medGEH":np.median(g),"R2":r2,"corr2":corr**2,"slope":slope,
            "meanbias_pct":100*np.mean((m-o)/o),"medbias_pct":100*np.median((m-o)/o),
            "meanbias_veh":np.mean(m-o)}

def main():
    print("building car-link GDF (parse network + linkstats x10)...")
    g=link_gdf()
    nloaded=(g.vol24>0).sum()
    print(f"car links: {len(g):,}   loaded (vol>0): {nloaded:,}")
    df,ntot=match_stations(g)
    df["GEH"]=geh(df.model_daily.values, df.obs_AADT.values)
    df["diff"]=df.model_daily-df.obs_AADT
    df["rel_err_pct"]=100*df["diff"]/df.obs_AADT
    (OUTDIR/"aadt").mkdir(parents=True,exist_ok=True)
    df.to_csv(OUTDIR/"aadt/aadt_validation_2023.csv", index=False)
    gm=int(df.geom_match.sum()); lm=int((df.model_daily>0).sum())
    print(f"\nAADT stations (AADT_2023>0): {ntot:,}")
    print(f"  geometric in-class match: {gm:,} ({100*gm/ntot:.1f}%)")
    print(f"  matched to LOADED link:   {lm:,} ({100*lm/ntot:.1f}%)")
    print("\n=== DAILY MATSim(x10) vs AADT 2023 ===")
    overall=summarize(df,"ALL")
    nonramp=summarize(df[df.facility!="Ramp"],"ALL mainline (excl ramps)")
    rows=[overall, nonramp]
    for grp in GROUP_ORDER+["Ramp"]:
        s=summarize(df[df.facility==grp], grp)
        if s: rows.append(s)
    tab=pd.DataFrame(rows)
    pd.set_option("display.width",200,"display.max_columns",20)
    print(tab.to_string(index=False,
        formatters={c:(lambda v:f"{v:.2f}") for c in ["pctGEH5","pctGEH10","medGEH","R2","corr2","slope","meanbias_pct","medbias_pct","meanbias_veh"]}))
    tab.to_csv(OUTDIR/"aadt/summary_by_facility.csv", index=False)
    print(f"\nwrote {OUTDIR/'aadt/aadt_validation_2023.csv'}")
    print(f"wrote {OUTDIR/'aadt/summary_by_facility.csv'}")

if __name__=="__main__":
    main()
