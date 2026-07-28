#!/usr/bin/env python3
"""Hourly validation: MATSim it.64 hourly link volumes (x10) vs FHWA TMAS 2023 (weekday avg).

Parse TMAS .STA metadata (BMR stations), build a weekday-average 24h profile per station
from the 12 monthly .VOL files (sum lanes+directions, mean over Mon-Fri), match each station
to a loaded car-link pair, and compare the hourly profile: peak-hour GEH + profile correlation.
Writes tmas/tmas_validation_2023.csv + tmas/station_profiles.csv.
"""
import glob
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from netval2023_common import (ROOT, OUTDIR, CRS, link_gdf, geh,
                               FSYS_GROUP, FSYS_HWY, FSYS_TOL)

STA = ROOT/"data/tmas_2023/MD_2023 (TMAS).STA"
VOLGLOB = str(ROOT/"data/tmas_2023/md_vol/*.VOL")
HRS=[f"hour_{h:02d}" for h in range(24)]
WEEKDAYS={"2","3","4","5","6"}   # TMAS day_of_week: 1=Sun ... 7=Sat

def load_stations():
    sta=pd.read_csv(STA, sep="|", dtype=str)
    # one physical station may have many lane/dir rows; take first row's metadata per station_id
    sta["fs"]=sta.f_system.str[0].astype(int)
    sta["lat"]=sta.latitude.astype(float)/1e6
    sta["lon"]=-sta.longitude.astype(float)/1e6
    sta["route"]=pd.to_numeric(sta.posted_signed_route, errors="coerce")
    meta=sta.groupby("station_id").first().reset_index()
    return meta[["station_id","fs","lat","lon","route","station_location"]]

def load_weekday_profiles():
    """Per-station weekday-average 24h total volume profile (sum lanes+dirs, mean over weekdays)."""
    frames=[]
    for f in sorted(glob.glob(VOLGLOB)):
        v=pd.read_csv(f, sep="|", dtype=str)
        v=v[v.day_of_week.isin(WEEKDAYS)]
        for h in HRS: v[h]=pd.to_numeric(v[h], errors="coerce").fillna(0.0)
        frames.append(v[["station_id","month_record","day_record"]+HRS])
    vol=pd.concat(frames, ignore_index=True)
    # daily station total = sum across lanes+directions for that station/date
    daily=vol.groupby(["station_id","month_record","day_record"], as_index=False)[HRS].sum()
    # weekday-average profile per station
    prof=daily.groupby("station_id", as_index=False)[HRS].mean()
    prof["obs_daily"]=prof[HRS].sum(axis=1)
    prof["ndays"]=daily.groupby("station_id").size().values
    return prof

def match_station(s, g, sidx, gid, ghwy, gux, guy, gvol):
    fs=int(s.fs); tol=max(FSYS_TOL.get(fs,45.0),60.0); allowed=FSYS_HWY.get(fs,None)
    cand=list(sidx.query(s.pt.buffer(tol), predicate="intersects"))
    inclass=[]
    for idx in cand:
        lid=g.id.iloc[idx]; hw=ghwy[lid]
        if allowed is not None and hw not in allowed: continue
        d=s.pt.distance(gid[lid])
        if d<=tol: inclass.append((lid,d))
    if not inclass:
        near=[(g.id.iloc[idx], s.pt.distance(gid[g.id.iloc[idx]])) for idx in cand]
        inclass=[(lid,d) for lid,d in near if d<=60]
    loaded=[(lid,d) for lid,d in inclass if gvol[lid]>0]
    if not loaded: return [], np.nan
    loaded.sort(key=lambda t:t[1])
    prim,pd0=loaded[0]; ux,uy=gux[prim],guy[prim]
    opp=[(lid,d) for lid,d in loaded if lid!=prim and gux[lid]*ux+guy[lid]*uy<-0.3]
    opp.sort(key=lambda t:t[1])
    chosen=[prim]+([opp[0][0]] if opp else [])
    return chosen, pd0

def main():
    print("building car-link GDF...")
    g=link_gdf().reset_index(drop=True)
    sidx=g.sindex
    gid=dict(zip(g.id,g.geometry)); ghwy=dict(zip(g.id,g.hwy))
    gux=dict(zip(g.id,g.ux)); guy=dict(zip(g.id,g.uy)); gvol=dict(zip(g.id,g.vol24))
    ghr={lid:np.array([g[f"h{h}"].iloc[i] for h in range(24)]) for i,lid in enumerate(g.id)}

    meta=load_stations(); prof=load_weekday_profiles()
    df=meta.merge(prof, on="station_id", how="inner")
    print(f"TMAS stations with weekday volume data: {len(df)}")
    # reproject points to network CRS
    pts=gpd.GeoSeries([Point(xy) for xy in zip(df.lon,df.lat)], crs="EPSG:4326").to_crs(CRS)
    df=df.reset_index(drop=True); df["pt"]=pts.values

    rows=[]; profrows=[]
    for _,s in df.iterrows():
        chosen,dist=match_station(s,g,sidx,gid,ghwy,gux,guy,gvol)
        if not chosen: continue
        mprof=np.sum([ghr[l] for l in chosen], axis=0)
        oprof=s[HRS].values.astype(float)
        model_daily=mprof.sum(); obs_daily=oprof.sum()
        # peak hours from observed profile
        am=6+int(np.argmax(oprof[6:10])); pm=15+int(np.argmax(oprof[15:20]))
        geh_am=float(geh(mprof[am],oprof[am])); geh_pm=float(geh(mprof[pm],oprof[pm]))
        # profile shape correlation (24h)
        corr=np.corrcoef(mprof,oprof)[0,1] if mprof.std()>0 and oprof.std()>0 else np.nan
        rows.append({"station_id":s.station_id,"fs":int(s.fs),
                     "facility":FSYS_GROUP.get(int(s.fs),"Other"),"route":s.route,
                     "location":s.station_location,"n_links":len(chosen),"min_dist":dist,
                     "obs_daily":obs_daily,"model_daily":model_daily,
                     "am_peak_hr":am,"pm_peak_hr":pm,
                     "obs_am":oprof[am],"model_am":mprof[am],"geh_am":geh_am,
                     "obs_pm":oprof[pm],"model_pm":mprof[pm],"geh_pm":geh_pm,
                     "profile_corr":corr,"link_ids":";".join(chosen)})
        profrows.append({"station_id":s.station_id,"route":s.route,"fs":int(s.fs),
                         "location":s.station_location,
                         **{f"obs_h{h}":oprof[h] for h in range(24)},
                         **{f"mod_h{h}":mprof[h] for h in range(24)}})
    res=pd.DataFrame(rows)
    (OUTDIR/"tmas").mkdir(parents=True,exist_ok=True)
    res.to_csv(OUTDIR/"tmas/tmas_validation_2023.csv", index=False)
    pd.DataFrame(profrows).to_csv(OUTDIR/"tmas/station_profiles.csv", index=False)
    print(f"\nmatched TMAS stations (loaded links): {len(res)} of {len(df)}")
    print(f"mean profile correlation:  {res.profile_corr.mean():.3f}   median {res.profile_corr.median():.3f}")
    print(f"AM peak GEH: median {res.geh_am.median():.1f}   %<10 {100*(res.geh_am<10).mean():.0f}%")
    print(f"PM peak GEH: median {res.geh_pm.median():.1f}   %<10 {100*(res.geh_pm<10).mean():.0f}%")
    print(f"peak-hour bias: AM median {100*((res.model_am-res.obs_am)/res.obs_am).median():+.0f}%  "
          f"PM median {100*((res.model_pm-res.obs_pm)/res.obs_pm).median():+.0f}%")
    print("\nby facility (profile corr, median peak GEH):")
    print(res.groupby("facility").agg(n=("station_id","size"),
          prof_corr=("profile_corr","mean"),
          geh_am=("geh_am","median"),geh_pm=("geh_pm","median")).round(2).to_string())
    print(f"\nwrote {OUTDIR/'tmas/tmas_validation_2023.csv'}")

if __name__=="__main__":
    main()
