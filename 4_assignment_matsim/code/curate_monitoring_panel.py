#!/usr/bin/env python3
"""Curate the toll MONITORING-STATION PANEL: the AADT stations whose base->toll volume change (ΔV) we
track for the I-695 pricing Section-5 facility-impact result. Three groups:
  1. I-695 corridor  (priced facility; volume should DROP)   -- segmented NW/NE/SE/SW arc
  2. diversion routes (I-95,I-895,I-83,I-70,US-40,US-1,MD-2,MD-702,MD-43,MD-140,MD-26; should RISE)
  3. screenline       (I-695 cordon + radial cross-section)

Rigorously verifies each station->link match (geom_match flag, snap distance vs FHWA-class tolerance,
facility class, hwy type) so the locked-in link_ids give a trustworthy ΔV. base_vol/GEH here are the
reference from the cleaned AADT table (transitfix run); the base_hybrid validator refills base_vol from
the base_hybrid linkstats before the toll run.

Writes network_validation_2023/base_hybrid/monitoring_panel.csv.
"""
import re, math
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AADT = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
I695 = ROOT/"scenarios/toll_research/i695_link_ids.txt"
CORDON = ROOT/"network_validation_2023/screenline_stations_full_cordon.csv"
OUT  = ROOT/"network_validation_2023/base_hybrid"
FSYS_TOL = {1:80.0,2:75.0,3:55.0,4:45.0,5:40.0,6:40.0,7:40.0}   # snap tolerance (m) per F_SYSTEM

# diversion routes: (ID_PREFIX, ID_RTE_NO) mainline. Beltway toll pushes traffic onto these.
DIVERSION = {("IS",95):"I-95",("IS",895):"I-895",("IS",83):"I-83",("IS",70):"I-70",
             ("US",40):"US-40",("US",1):"US-1",("MD",2):"MD-2 (Ritchie)",("MD",702):"MD-702",
             ("MD",43):"MD-43",("MD",140):"MD-140",("MD",26):"MD-26"}

def i695_links():
    s=set()
    for ln in I695.read_text().splitlines():
        ln=ln.strip()
        if ln and not ln.startswith("#"): s.add(ln)
    return s

def arc_of(lon,lat,clon,clat):
    ang=math.degrees(math.atan2(lat-clat, lon-clon))     # 0=E, 90=N, 180=W, -90=S
    if   0<=ang<90:  return "NE"
    if  90<=ang<=180:return "NW"
    if -90<=ang<0:   return "SE"
    return "SW"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df=pd.read_csv(AADT)
    df["lset"]=df.link_ids.astype(str).apply(lambda s:set(x for x in s.split(";") if x and x!="nan"))
    i695=i695_links()
    print(f"AADT stations {len(df)}, I-695 links {len(i695)}")

    is695 = df.lset.apply(lambda s: len(s & i695)>0) | \
            df.ROADNAME.astype(str).str.contains("BELTWAY|IS 695|I-695|MD 695", case=False, na=False)
    is695 &= (df.ID_PREFIX!="RP")                         # mainline only, drop ramps
    g695=df[is695].copy()
    clon,clat=g695.lon.mean(),g695.lat.mean()
    g695["group"]="I-695"; g695["segment"]=[arc_of(r.lon,r.lat,clon,clat) for r in g695.itertuples()]
    g695["road"]="I-695 Beltway"

    key=list(zip(df.ID_PREFIX, pd.to_numeric(df.ID_RTE_NO,errors="coerce").fillna(-1).astype(int)))
    df["_key"]=key
    isdiv = df._key.apply(lambda k: k in DIVERSION) & (df.ID_PREFIX!="RP") & (~is695)
    gdiv=df[isdiv].copy()
    gdiv["group"]="diversion"; gdiv["segment"]=""; gdiv["road"]=gdiv._key.map(DIVERSION)

    cordon=set(pd.read_csv(CORDON).station.astype(str))
    isscr = df.LOCATION_ID.astype(str).isin(cordon) & (~is695) & (~isdiv)
    gscr=df[isscr].copy()
    gscr["group"]="screenline"; gscr["segment"]=""; gscr["road"]=gscr.ROADNAME

    panel=pd.concat([g695,gdiv,gscr], ignore_index=True)
    # rigorous match QA
    tol=df.F_SYSTEM.map(FSYS_TOL)
    panel["tol_m"]=panel.F_SYSTEM.map(FSYS_TOL)
    panel["ratio"]=panel.model_daily/panel.obs_AADT.replace(0,np.nan)
    panel["match_ok"]=(panel.geom_match==1) & (panel.min_dist<=panel.tol_m) & (panel.facility!="Ramp") \
                      & (panel.model_daily>0)
    cols=["LOCATION_ID","group","segment","road","ROADNAME","facility","F_SYSTEM","hwy","lon","lat",
          "link_ids","n_links","min_dist","tol_m","geom_match","obs_AADT","model_daily","GEH","ratio","match_ok"]
    panel=panel[cols].rename(columns={"LOCATION_ID":"station_id","model_daily":"base_vol_ref"})
    panel.to_csv(OUT/"monitoring_panel.csv", index=False)

    print(f"\nwrote {OUT/'monitoring_panel.csv'}  ({len(panel)} stations)")
    for g in ["I-695","diversion","screenline"]:
        sub=panel[panel.group==g]; ok=sub.match_ok.sum()
        print(f"\n=== {g}: {len(sub)} stations, {ok} match_ok ===")
        if g=="I-695":
            print(sub.groupby("segment").agg(n=("station_id","size"),ok=("match_ok","sum"),
                  med_ratio=("ratio","median")).to_string())
        else:
            print(sub.groupby("road").agg(n=("station_id","size"),ok=("match_ok","sum"),
                  med_ratio=("ratio","median")).to_string())
    print(f"\nOVERALL median model/obs ratio (match_ok): {panel[panel.match_ok].ratio.median():.3f}")

if __name__=="__main__":
    main()
