#!/usr/bin/env python3
"""Step 1: parse MATSim network -> node/link arrays + graph; build I-95 corridor
milepost mapping (axis projection, SW=DC -> NE=Delaware); select GPS trips (mode 0)
whose straight O->D line crosses the I-95 corridor buffer. Caches everything to cache/."""
import gzip, os, math, xml.etree.ElementTree as ET
import numpy as np, pandas as pd
from shapely.geometry import LineString, Point, MultiLineString
from shapely.strtree import STRtree
from shapely.ops import unary_union
from shapely import prepared
from pyproj import Transformer

BASE = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
SCEN = f"{BASE}/scenarios/02_i695_congestion_pricing"
NET  = f"{SCEN}/output_base/base_hybrid/output_network.xml.gz"
I95IDS = f"{SCEN}/via_i95/i95_link_ids.txt"
GPS  = f"{BASE}/input/WMA_device_TripRosters_20220504.csv"
OUT  = f"{BASE}/network_validation_2023/FINAL_FIGURES/i95_gps_vs_model/cache"
CRS  = "EPSG:26985"
os.makedirs(OUT, exist_ok=True)
M2MI = 1.0 / 1609.344

# ---- 1. parse network ------------------------------------------------------
print("parsing network...", flush=True)
nodes = {}       # id -> (x,y)
links = {}       # id -> dict
ctx = ET.iterparse(gzip.open(NET, "rb"), events=("end",))
for ev, el in ctx:
    if el.tag == "node":
        nodes[el.get("id")] = (float(el.get("x")), float(el.get("y")))
    elif el.tag == "link":
        modes = el.get("modes") or ""
        links[el.get("id")] = dict(frm=el.get("from"), to=el.get("to"),
                                   length=float(el.get("length")),
                                   free=float(el.get("freespeed")),
                                   modes=modes)
        el.clear()
print(f"  {len(nodes)} nodes, {len(links)} links", flush=True)

# node index arrays
nid_list = list(nodes.keys())
nid_idx = {n: i for i, n in enumerate(nid_list)}
nx_arr = np.array([nodes[n][0] for n in nid_list])
ny_arr = np.array([nodes[n][1] for n in nid_list])

# car links only, build edge arrays for graph
lid_list, u_arr, v_arr, w_arr, len_arr, free_arr = [], [], [], [], [], []
for lid, L in links.items():
    if "car" not in L["modes"].split(","):
        continue
    if L["frm"] not in nid_idx or L["to"] not in nid_idx:
        continue
    lid_list.append(lid)
    u_arr.append(nid_idx[L["frm"]]); v_arr.append(nid_idx[L["to"]])
    fs = max(L["free"], 0.1)
    w_arr.append(L["length"] / fs)   # free-flow travel time (s)
    len_arr.append(L["length"]); free_arr.append(fs)
u_arr = np.array(u_arr); v_arr = np.array(v_arr)
w_arr = np.array(w_arr); len_arr = np.array(len_arr); free_arr = np.array(free_arr)
lid_arr = np.array(lid_list)
lid_edge_idx = {lid: i for i, lid in enumerate(lid_list)}   # link id -> edge row
print(f"  car edges: {len(lid_list)}", flush=True)

# ---- 2. I-95 corridor milepost ---------------------------------------------
i95_ids = [l.strip() for l in open(I95IDS) if l.strip()]
i95_ids = [l for l in i95_ids if l in links and links[l]["frm"] in nodes and links[l]["to"] in nodes]
# axis SW (DC) -> NE (Delaware) using from-nodes
pts = [nodes[links[l]["frm"]] for l in i95_ids]
sw = min(pts, key=lambda p: p[0] + p[1]); ne = max(pts, key=lambda p: p[0] + p[1])
axis = np.array([ne[0] - sw[0], ne[1] - sw[1]]); axis = axis / np.linalg.norm(axis)
sw = np.array(sw)
i95_mp = {}     # link id -> milepost (miles along corridor at link midpoint)
i95_dir = {}    # link id -> NB/SB
i95_geom = []
for lid in i95_ids:
    x0, y0 = nodes[links[lid]["frm"]]; x1, y1 = nodes[links[lid]["to"]]
    mid = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    mp = np.dot(mid - sw, axis) * M2MI
    i95_mp[lid] = mp
    proj = (x1 - x0) * axis[0] + (y1 - y0) * axis[1]
    i95_dir[lid] = "NB" if proj > 0 else "SB"
    i95_geom.append(LineString([(x0, y0), (x1, y1)]))
i95_set = set(i95_ids)
mps = np.array(list(i95_mp.values()))
print(f"  I-95 links used: {len(i95_ids)}  milepost range {mps.min():.1f}..{mps.max():.1f} mi", flush=True)

# corridor buffer (union of I-95 links, buffered 3 km) for GPS pre-selection
corridor = unary_union(i95_geom)
corridor_buf = corridor.buffer(3000.0)
pcorr = prepared.prep(corridor_buf)
# corridor axis endpoints in projected coords for the "opposite side of Baltimore cordon" idea
# baltimore cordon at ~ mid corridor; along-axis coordinate of DC end and Delaware end
corr_lo, corr_hi = mps.min(), mps.max()

# ---- 3. GPS selection ------------------------------------------------------
print("loading GPS...", flush=True)
df = pd.read_csv(GPS, usecols=["latitude_1","longitude_1","utc_timestamp_1","utc_offset_1",
                               "latitude_2","longitude_2","utc_timestamp_2","linked_trip_mode"])
n_all = len(df)
df = df[df.linked_trip_mode == 0].copy()
print(f"  total {n_all}, mode0 {len(df)}", flush=True)

tr = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
ox, oy = tr.transform(df.longitude_1.values, df.latitude_1.values)
dx, dy = tr.transform(df.longitude_2.values, df.latitude_2.values)
df["ox"], df["oy"], df["dx"], df["dy"] = ox, oy, dx, dy

# straight O->D line crosses corridor buffer?
def crosses(ox, oy, dx, dy):
    ln = LineString([(ox, oy), (dx, dy)])
    return pcorr.intersects(ln)

mask = np.zeros(len(df), dtype=bool)
oxv, oyv, dxv, dyv = df.ox.values, df.oy.values, df.dx.values, df.dy.values
# quick bbox prune vs corridor bbox
cminx, cminy, cmaxx, cmaxy = corridor_buf.bounds
for i in range(len(df)):
    # both endpoints far outside corridor bbox on same side -> skip line build
    if (oxv[i] < cminx and dxv[i] < cminx) or (oxv[i] > cmaxx and dxv[i] > cmaxx) \
       or (oyv[i] < cminy and dyv[i] < cminy) or (oyv[i] > cmaxy and dyv[i] > cmaxy):
        continue
    if pcorr.intersects(LineString([(oxv[i], oyv[i]), (dxv[i], dyv[i])])):
        mask[i] = True
cand = df[mask].copy()
print(f"  GPS candidates (straight line crosses I-95 3km buffer): {len(cand)}", flush=True)

# local departure seconds-of-day
loc = (cand.utc_timestamp_1.values + cand.utc_offset_1.values)
cand["dep_sod"] = loc % 86400

# ---- 4. save cache ---------------------------------------------------------
np.savez(f"{OUT}/net.npz",
         nx=nx_arr, ny=ny_arr, u=u_arr, v=v_arr, w=w_arr, ln=len_arr, free=free_arr,
         lid=lid_arr, nid=np.array(nid_list),
         sw=sw, axis=axis, corr_lo=corr_lo, corr_hi=corr_hi)
# I-95 edge-index -> milepost/dir maps as arrays aligned to edge rows
i95_edge = np.array([lid_edge_idx[l] for l in i95_ids if l in lid_edge_idx])
i95_edge_mp = np.array([i95_mp[l] for l in i95_ids if l in lid_edge_idx])
np.savez(f"{OUT}/i95.npz",
         i95_lids=np.array(i95_ids),
         i95_mp=np.array([i95_mp[l] for l in i95_ids]),
         i95_dir=np.array([i95_dir[l] for l in i95_ids]),
         i95_edge=i95_edge, i95_edge_mp=i95_edge_mp)
cand.to_parquet(f"{OUT}/gps_candidates.parquet")
import json
json.dump({"n_all": int(n_all), "n_mode0": int(len(df)), "n_candidates": int(len(cand)),
           "mp_min": float(mps.min()), "mp_max": float(mps.max()),
           "n_i95_links": len(i95_ids)}, open(f"{OUT}/select_stats.json","w"), indent=2)
print("saved cache.", flush=True)
