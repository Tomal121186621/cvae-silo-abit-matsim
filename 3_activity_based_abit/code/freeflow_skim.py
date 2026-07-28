#!/usr/bin/env python3
"""Network-consistent FREE-FLOW auto skim (all car links at freespeed) using the SAME network + zone
centroids + Dijkstra as skim_from_events.py. Used as the apples-to-apples baseline to show the feedback
loop's congested skim has HIGHER travel times than free flow (isolating congestion from skim-source
differences vs the MITO free-flow OMX). Usage: python freeflow_skim.py <out_skim.omx>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/code")))
import numpy as np, pandas as pd
import skim_from_events as SE
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import openmatrix as omx

def main(out_path):
    nodes, L = SE.parse_network()
    nid=list(nodes); nidx={n:i for i,n in enumerate(nid)}
    nxy=np.array([nodes[n] for n in nid])
    free_s=L["length"]/np.maximum(L["free"],0.1)                 # ALL links free-flow seconds
    fi=np.array([nidx[f] for f in L["frm"]]); ti=np.array([nidx[t] for t in L["to"]])
    G=csr_matrix((free_s,(fi,ti)), shape=(len(nid),len(nid)))
    zc=pd.read_csv(SE.ZONES); zones=zc.zone.to_numpy(int); zxy=zc[["coordX","coordY"]].to_numpy()
    tree=cKDTree(nxy); d,nn=tree.query(zxy,k=1); innet=d<=SE.MAX_SNAP
    src=nn[innet]; n=len(src); tmin=np.full((n,n),np.nan)
    for s in range(0,n,250):
        dist=dijkstra(G, directed=True, indices=src[s:s+250]); tmin[s:s+250,:]=dist[:,src]/60.0
    full=np.full((len(zones),len(zones)),180.0); on=np.where(innet)[0]
    for a,ia in enumerate(on):
        g=np.isfinite(tmin[a]); full[ia,on]=np.where(g,tmin[a],180.0)
    if Path(out_path).exists(): Path(out_path).unlink()
    of=omx.open_file(str(out_path),"w"); of["mat1"]=full.astype(np.float32)
    of.create_mapping("origins",zones.tolist()); of.create_mapping("destinations",zones.tolist()); of.close()
    print(f"free-flow network skim -> {out_path}  mean on-net {tmin[np.isfinite(tmin)].mean():.1f} min")

if __name__=="__main__":
    main(sys.argv[1])
