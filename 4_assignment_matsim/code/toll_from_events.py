#!/usr/bin/env python3
"""Per-OD road-pricing TOLL skim ($) from a tolled MATSim run — the money-side bridge for the hybrid
ABIT<->MATSim pricing loop. Companion to skim_from_events.py (which does travel time).

For every CAR trip in the run it sums the RoadPricing money events (personMoney, negative $) paid during
that leg, maps the trip's origin/destination link to the nearest zone, and averages over all car trips on
each OD -> a TRIP-TIMING-WEIGHTED DAILY-AVERAGE per-OD toll (peak trips pay peak rates, so the mean over
actual trips is naturally timing-weighted). Car trips that used no tolled link count as $0, so the OD mean
reflects the fraction of trips that actually use I-695. This daily average feeds ABIT's (period-agnostic)
mode choice; MATSim's inner loop keeps the full time-of-day toll for route + departure-time choice.

Usage: python toll_from_events.py <events.xml.gz> <out_toll.omx> [zones_template.omx]
Writes toll_auto.omx: matrix mat1 = $/car-trip, 1588x1588, origins/destinations = zone ids.
"""
import sys, gzip, re
from pathlib import Path
import numpy as np, pandas as pd, openmatrix as omx

ROOT  = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
NET   = ROOT/"scenarios/01_base_no_pricing/input/network/bmr_network_pt_speedcal.xml.gz"
ZONES = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Tour Based MITO/data/zone_coords.csv")
MAX_SNAP = 4000.0   # m: link farther than this from any zone centroid -> its trips are dropped

def link_midpoints():
    """map each car link id -> (x,y) midpoint of its from/to nodes."""
    nodes={}
    nre=re.compile(r'<node id="([^"]+)" x="([^"]+)" y="([^"]+)"')
    lre=re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)".*?modes="([^"]+)"')
    mids={}
    frm={}; to={}
    with gzip.open(NET,"rt") as f:
        for line in f:
            m=nre.search(line)
            if m: nodes[m.group(1)]=(float(m.group(2)),float(m.group(3))); continue
            m=lre.search(line)
            if m and "car" in m.group(6).split(","):
                frm[m.group(1)]=m.group(2); to[m.group(1)]=m.group(3)
    for lid,a in frm.items():
        b=to[lid]
        if a in nodes and b in nodes:
            mids[lid]=((nodes[a][0]+nodes[b][0])/2.0,(nodes[a][1]+nodes[b][1])/2.0)
    return mids

def link_to_zone(mids, zones, zxy):
    from scipy.spatial import cKDTree
    tree=cKDTree(zxy)
    lids=list(mids); lxy=np.array([mids[l] for l in lids])
    d,nn=tree.query(lxy, k=1)
    lz={}
    for i,l in enumerate(lids):
        lz[l]= int(zones[nn[i]]) if d[i]<=MAX_SNAP else -1
    return lz

def extract(events_path):
    """-> dict (Ozone,Dzone) -> [toll_sum, trip_count] over car trips."""
    active={}                                  # person -> [origin_link, toll_accum]
    trips=[]                                   # (origin_link, dest_link, toll)
    dep=re.compile(r'type="departure"'); arr=re.compile(r'type="arrival"'); mon=re.compile(r'type="personMoney"')
    pre=re.compile(r'person="([^"]+)"'); lre=re.compile(r'link="([^"]+)"')
    mre=re.compile(r'legMode="([^"]+)"'); are=re.compile(r'amount="(-?[0-9.eE]+)"')
    opn=gzip.open if str(events_path).endswith(".gz") else open
    with opn(events_path,"rt") as f:
        for line in f:
            isdep='type="departure"' in line; isarr='type="arrival"' in line; ismon='type="personMoney"' in line
            if not (isdep or isarr or ismon): continue
            pm=pre.search(line)
            if not pm: continue
            per=pm.group(1)
            if ismon:
                if per in active:
                    am=are.search(line)
                    if am:
                        v=float(am.group(1))
                        if v<0: active[per][1]+= -v     # toll paid ($)
                continue
            mm=mre.search(line)
            if not mm or mm.group(1)!="car": continue
            lm=lre.search(line)
            if isdep:
                active[per]=[lm.group(1) if lm else None, 0.0]
            else:  # arrival on a car leg
                st=active.pop(per,None)
                if st is not None and lm:
                    trips.append((st[0], lm.group(1), st[1]))
    return trips

def main():
    ev=sys.argv[1]; out=sys.argv[2]
    zc=pd.read_csv(ZONES); zones=zc.zone.to_numpy(int); zxy=zc[["coordX","coordY"]].to_numpy()
    mids=link_midpoints(); lz=link_to_zone(mids, zones, zxy)
    print(f"car links mapped to zones: {len(lz):,}", flush=True)
    trips=extract(ev)
    print(f"car trips parsed: {len(trips):,}", flush=True)

    zidx={int(z):i for i,z in enumerate(zones)}
    nz=len(zones)
    tsum=np.zeros((nz,nz)); tcnt=np.zeros((nz,nz))
    tolled_trips=0; toll_total=0.0
    for oL,dL,toll in trips:
        oz=lz.get(oL,-1); dz=lz.get(dL,-1)
        if oz<0 or dz<0: continue
        i=zidx[oz]; j=zidx[dz]; tsum[i,j]+=toll; tcnt[i,j]+=1
        if toll>0: tolled_trips+=1; toll_total+=toll
    with np.errstate(invalid="ignore",divide="ignore"):
        tavg=np.where(tcnt>0, tsum/np.maximum(tcnt,1), 0.0)
    print(f"OD pairs with car trips: {(tcnt>0).sum():,}", flush=True)
    print(f"trips paying toll: {tolled_trips:,} / {len(trips):,} ; total ${toll_total:,.0f} ; "
          f"mean toll over paying trips ${toll_total/max(tolled_trips,1):.2f}", flush=True)

    if Path(out).exists(): Path(out).unlink()
    of=omx.open_file(str(out),"w"); of["mat1"]=tavg.astype(np.float32)
    of.create_mapping("origins", zones.tolist()); of.create_mapping("destinations", zones.tolist()); of.close()
    print(f"wrote {out}  (per-OD daily-average $/car-trip)", flush=True)

if __name__=="__main__":
    main()
