#!/usr/bin/env python3
"""Congested zone-to-zone AUTO travel-time skim from a MATSim run — the feedback bridge that turns the
assignment's realised (congested) link travel times back into an OD skim the demand model can consume.

Pipeline:
  1. parse the car network  -> nodes (x,y) + directed car links (from,to,length,freespeed)
  2. parse output_events     -> per-link mean *realised* travel time (left-link minus entered-link),
                                averaged over the whole day; links never used keep free-flow length/freespeed
  3. map each zone centroid  -> nearest network node (KDTree)
  4. shortest paths (scipy sparse Dijkstra) between zone-centroid nodes on the congested graph
  5. write traveltime_auto.omx (minutes, 1588x1588, origins/destinations mappings) — same schema the
     apply engine already reads; OD pairs whose zones aren't near the network keep the prior skim.

Usage: python skim_from_events.py <events.xml.gz> <out_skim.omx> [prior_skim.omx]
"""
import sys, gzip, re, os
from pathlib import Path
import numpy as np, pandas as pd, openmatrix as omx

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
# Network must MATCH the run that produced the events (link ids). The hybrid runs on the speed-calibrated
# network, so default to it; override with TBM_NET if a run used a different network.
NET  = Path(os.environ.get("TBM_NET",
        str(ROOT/"scenarios/01_base_no_pricing/input/network/bmr_network_pt_speedcal.xml.gz")))
ZONES= Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Tour Based MITO/data/zone_coords.csv")
MAX_SNAP = 4000.0   # m: a zone whose centroid is farther than this from any node is "off-network" (keep prior)

def parse_network():
    nodes={}
    lid=[]; lfrom=[]; lto=[]; llen=[]; lfree=[]
    nre=re.compile(r'<node id="([^"]+)" x="([^"]+)" y="([^"]+)"')
    lre=re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)".*?modes="([^"]+)"')
    with gzip.open(NET,"rt") as f:
        for line in f:
            m=nre.search(line)
            if m: nodes[m.group(1)]=(float(m.group(2)),float(m.group(3))); continue
            m=lre.search(line)
            if m and "car" in m.group(6).split(","):
                lid.append(m.group(1)); lfrom.append(m.group(2)); lto.append(m.group(3))
                llen.append(float(m.group(4))); lfree.append(float(m.group(5)))
    return nodes, dict(id=lid, frm=lfrom, to=lto, length=np.array(llen), free=np.array(lfree))

def link_congested_tt(events_path, link_ids):
    """mean realised travel time (s) per link over the day; links unused -> NaN (caller uses free-flow)."""
    want=set(link_ids)
    ent={}                                   # (veh,link) -> entered time (last)
    tot={l:0.0 for l in link_ids}; cnt={l:0 for l in link_ids}
    en=re.compile(r'type="entered link"'); lv=re.compile(r'type="left link"')
    linkre=re.compile(r'link="([^"]+)"'); vre=re.compile(r'vehicle="([^"]+)"'); tre=re.compile(r'time="([0-9.]+)"')
    opn=gzip.open if str(events_path).endswith(".gz") else open
    with opn(events_path,"rt") as f:
        for line in f:
            isen="entered link" in line; islv="left link" in line
            if not (isen or islv): continue
            lm=linkre.search(line)
            if not lm or lm.group(1) not in want: continue
            vm=vre.search(line); tm=tre.search(line)
            if not vm or not tm: continue
            l=lm.group(1); key=(vm.group(1),l); t=float(tm.group(1))
            if isen: ent[key]=t
            else:
                t0=ent.pop(key,None)
                if t0 is not None and t>=t0: tot[l]+=t-t0; cnt[l]+=1
    tt={}
    for l in link_ids:
        tt[l]=tot[l]/cnt[l] if cnt[l]>0 else np.nan
    return tt

def build_skim(events_path, out_path, prior_path=None):
    from scipy.spatial import cKDTree
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    nodes, L = parse_network()
    nid=list(nodes); nidx={n:i for i,n in enumerate(nid)}
    nxy=np.array([nodes[n] for n in nid])
    print(f"network: {len(nid):,} car nodes, {len(L['id']):,} car links")

    ctt=link_congested_tt(events_path, L["id"])
    free_s=L["length"]/np.maximum(L["free"],0.1)                       # free-flow sec
    w=np.array([ctt[l] if not np.isnan(ctt[l]) else free_s[i] for i,l in enumerate(L["id"])])
    used=np.sum([1 for l in L["id"] if not np.isnan(ctt[l])])
    print(f"links with realised times: {used:,}/{len(L['id']):,}  (rest free-flow)")
    fi=np.array([nidx[f] for f in L["frm"]]); ti=np.array([nidx[t] for t in L["to"]])
    G=csr_matrix((w,(fi,ti)), shape=(len(nid),len(nid)))

    zc=pd.read_csv(ZONES); zones=zc.zone.to_numpy(int); zxy=zc[["coordX","coordY"]].to_numpy()
    tree=cKDTree(nxy); d,nn=tree.query(zxy, k=1)
    innet=d<=MAX_SNAP
    print(f"zones on-network (snap<{MAX_SNAP:.0f}m): {innet.sum():,}/{len(zones):,}")
    src_nodes=nn[innet]                                                # node idx per on-network zone
    # Dijkstra from on-network zone nodes (batched to bound memory)
    n=len(src_nodes); tmin=np.full((n,n),np.nan)
    B=250
    for s in range(0,n,B):
        dist=dijkstra(G, directed=True, indices=src_nodes[s:s+B])      # (b x n_nodes) seconds
        tmin[s:s+B,:]=dist[:, src_nodes]/60.0                          # -> minutes, target = zone nodes
        print(f"  dijkstra {min(s+B,n)}/{n}")
    # assemble full 1588x1588 skim, seeded from prior (free-flow) where available
    zidx={int(z):i for i,z in enumerate(zones)}
    full=np.full((len(zones),len(zones)),np.nan)
    if prior_path and Path(prior_path).exists():
        pf=omx.open_file(str(prior_path),"r"); pm=np.array(pf[pf.list_matrices()[0]])
        pmap={int(z):int(i) for z,i in pf.mapping(pf.list_mappings()[0]).items()}; pf.close()
        for z,i in zidx.items():
            if z in pmap:
                for z2,j in zidx.items():
                    if z2 in pmap: full[i,j]=pm[pmap[z],pmap[z2]]
    on=np.where(innet)[0]
    for a,ia in enumerate(on):
        good=np.isfinite(tmin[a])                                     # finite path -> use it; else keep prior
        full[ia,on]=np.where(good, tmin[a], full[ia,on])
    full=np.where(np.isfinite(full),full,180.0)                       # unreachable / no-prior -> cap
    # write OMX (same schema as input skims)
    if Path(out_path).exists(): Path(out_path).unlink()
    of=omx.open_file(str(out_path),"w"); of["mat1"]=full.astype(np.float32)
    of.create_mapping("origins", zones.tolist()); of.create_mapping("destinations", zones.tolist())
    of.close()
    fin=np.isfinite(tmin)
    print(f"wrote {out_path}  on-net OD pairs reachable {100*fin.mean():.0f}%  mean {tmin[fin].mean():.1f} min")
    return full

if __name__=="__main__":
    ev=sys.argv[1]; out=sys.argv[2]; prior=sys.argv[3] if len(sys.argv)>3 else None
    build_skim(ev,out,prior)
