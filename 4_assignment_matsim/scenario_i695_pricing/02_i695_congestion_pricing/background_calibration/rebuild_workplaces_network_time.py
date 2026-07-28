#!/usr/bin/env python3
"""Workplace re-draw with NETWORK-TIME impedance (replaces the beeline draw of
ABIT/code/workplace_reassign.py, which was water-blind: Baltimore County wraps the
harbor, so beeline gravity created excess cross-harbor commutes).

Same LODES county->county flow constraints, same job-density attraction, same gravity
form; only the deterrence becomes exp(-beta * t_ij) with t_ij = CONGESTED AM (7-8h)
car shortest-path time through the frozen-base network. The harbor discourages
crossings by physics (3 tolled crossings, longer congested paths), not by any
artificial barrier term -- observed crossing counts are NOT used, so the harbor
screenline stays a genuine out-of-sample validation.

Outputs (into this folder):
  worker_workplace_zone_v2.csv   person_id, home_zone, work_zone_old, work_zone_new
  rebuild_report.txt             cross-harbor + commute-length diagnostics
"""
import ast, gzip, sys
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd
from pathlib import Path
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
BG = ROOT / "scenarios/02_i695_congestion_pricing/background_calibration"
SILO = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/scenOutput/updated_vae_calib5/microData")
NET = ROOT / "network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz"
LSF = ROOT / "scenarios/01_base_no_pricing/output_calib_fs/pass8/ITERS/it.10/10.linkstats.txt.gz"
ZS = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/inputs/zoneSystem.csv")
ZC = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Tour Based MITO/data/zone_coords.csv")
LODES_OD = BG / "lodes_county_od.csv"   # copied from the ABIT-era scratchpad if present
BETA = 0.10   # min^-1 on congested network time (recheck vs RTS commute lengths)
SEED = 20230

# ---------- congested AM travel time per link ----------
print("loading linkstats AM travel times ...", flush=True)
ls = pd.read_csv(LSF, sep="\t", low_memory=False, dtype={"LINK": str})
tt = dict(zip(ls.LINK, pd.to_numeric(ls["TRAVELTIME7-8avg"], errors="coerce")))

print("parsing network ...", flush=True)
nid = {}; coords = []
edges_r, edges_c, edges_w = [], [], []
for _, el in ET.iterparse(gzip.open(NET, "rb"), events=("end",)):
    if el.tag == "node":
        nid[el.get("id")] = len(coords); coords.append((float(el.get("x")), float(el.get("y"))))
        el.clear(); continue
    if el.tag != "link": el.clear(); continue
    if "car" in el.get("modes", ""):
        f, t = nid[el.get("from")], nid[el.get("to")]
        length, fs = float(el.get("length")), float(el.get("freespeed"))
        w = tt.get(el.get("id"))
        if w is None or not np.isfinite(w) or w <= 0: w = length / max(fs, 1e-3)
        edges_r.append(f); edges_c.append(t); edges_w.append(w / 60.0)  # minutes
    el.clear()
coords = np.array(coords)
G = csr_matrix((edges_w, (edges_r, edges_c)), shape=(len(coords), len(coords)))
print(f"graph: {len(coords):,} nodes, {len(edges_w):,} car edges", flush=True)

# ---------- zones -> nearest network node ----------
zs = pd.read_csv(ZS); z2c = dict(zip(zs["ZoneId"], zs["COUNTYFIPS"]))
zc = pd.read_csv(ZC).set_index("zone")
from scipy.spatial import cKDTree
tree = cKDTree(coords)
zc = zc[zc.index.isin(z2c)]
_, znode = tree.query(np.c_[zc.coordX, zc.coordY])
zones = zc.index.to_numpy()
zi = {z: i for i, z in enumerate(zones)}
print(f"{len(zones)} zones mapped to network nodes", flush=True)

# ---------- SILO workers/jobs ----------
dd = pd.read_csv(SILO / "dd_2023.csv", usecols=["hhID", "zone"]); hz = dict(zip(dd.hhID, dd.zone))
pp = pd.read_csv(SILO / "pp_2023.csv", usecols=["id", "hhid", "occupation"])
pp = pp[pp.occupation == 1].copy(); pp["homez"] = pp["hhid"].map(hz)
pp = pp.dropna(subset=["homez"]); pp["homez"] = pp.homez.astype(int)
pp = pp[pp.homez.isin(zi)]; pp["hc"] = pp.homez.map(z2c)
jj = pd.read_csv(SILO / "jj_2023.csv", usecols=["zone"])
jobs_z = jj.groupby("zone").size(); jobs_z = jobs_z[jobs_z.index.isin(zi)]
print(f"workers {len(pp):,}, jobs {jobs_z.sum():,}", flush=True)

# ---------- LODES county OD ----------
lod = pd.read_csv(LODES_OD)
counties = set(z2c.values())
lod = lod[lod.home_county.isin(counties) & lod.work_county.isin(counties)]

# ---------- shortest-path times from every HOME zone with workers ----------
home_zones = sorted(pp.homez.unique())
src_nodes = np.array([znode[zi[z]] for z in home_zones])
print(f"dijkstra from {len(home_zones)} home zones (chunked) ...", flush=True)
Tz = np.empty((len(home_zones), len(zones)))
CH = 64
for k in range(0, len(src_nodes), CH):
    D = dijkstra(G, indices=src_nodes[k:k+CH])
    Tz[k:k+CH] = D[:, znode]
    if k % 512 == 0: print(f"  {k}/{len(src_nodes)}", flush=True)
hzi = {z: i for i, z in enumerate(home_zones)}
print("time matrix done", flush=True)

# ---------- LODES-flow-driven draw, network-time deterrence ----------
rng = np.random.default_rng(SEED)
jz = pd.DataFrame({"zone": jobs_z.index, "jobs": jobs_z.values})
jz["wc"] = jz.zone.map(z2c)
wc_zone = {wc: (g.zone.to_numpy(), g.jobs.to_numpy(float)) for wc, g in jz.groupby("wc")}
scale = len(pp) / lod.groupby("home_county").workers.sum().reindex(pp.hc.value_counts().index).sum() if "workers" in lod.columns else None
wcol = "workers" if "workers" in lod.columns else lod.columns[-1]

# SURGICAL: keep each worker's v1 work COUNTY (and out-of-scope -1 status) exactly;
# re-draw only the ZONE within that county with network-time gravity.
v1 = pd.read_csv(BG / "worker_workplace_zone_v1.csv")
v1_wz = dict(zip(v1.person_id, v1.work_zone))
pp["wz1"] = pp.id.map(v1_wz)
pp = pp[pp.wz1.notna() & (pp.wz1 > 0)].copy()          # -1 / unmapped workers keep v1 as-is
pp["wc"] = pp.wz1.astype(int).map(z2c)
pp = pp[pp.wc.notna()]
print(f"minimal-transport repair over {len(pp):,} in-scope workers", flush=True)
# per (home zone, work county) cell: move ONLY the surplus in over-represented zones
# (vs the network-time gravity target) to under-represented zones. Everyone else keeps v1.
assign = {}          # only movers get entries
n_moved = 0
for (hz_, wc), gg in pp.groupby(["homez", "wc"]):
    zz, jw = wc_zone.get(wc, (None, None))
    if zz is None: continue
    zcols = np.array([zi[z] for z in zz])
    t = Tz[hzi[hz_], zcols]
    pr = jw * np.exp(-BETA * np.minimum(t, 240.0))
    ssum = pr.sum()
    pr = (jw / jw.sum()) if (not np.isfinite(ssum) or ssum <= 0) else pr / ssum
    n = len(gg)
    # target integer counts (largest remainder)
    exp_ = pr * n
    tgt = np.floor(exp_).astype(int)
    rem = n - tgt.sum()
    if rem > 0: tgt[np.argsort(-(exp_ - tgt))[:rem]] += 1
    zpos = {z: k for k, z in enumerate(zz)}
    cur = np.zeros(len(zz), dtype=int)
    wz1 = gg.wz1.astype(int).to_numpy()
    for z in wz1:
        k = zpos.get(z)
        if k is not None: cur[k] += 1
    surplus = cur - tgt
    donors = []          # worker indices to move
    ids_ = gg.id.to_numpy()
    for k in np.where(surplus > 0)[0]:
        members = np.where(wz1 == zz[k])[0]
        take = rng.choice(members, size=surplus[k], replace=False)
        donors.extend(take)
    # unmapped zones (v1 zone not in this county list) are also donors
    unmapped = [i for i, z in enumerate(wz1) if z not in zpos]
    donors.extend(unmapped)
    deficit = np.where(surplus < 0)[0]
    slots = np.repeat(zz[deficit], -surplus[deficit])
    rng.shuffle(slots)
    for i, znew in zip(donors, slots):
        assign[ids_[i]] = int(znew); n_moved += 1
print(f"moved {n_moved:,} workers ({100*n_moved/len(pp):.1f}%); all others keep v1", flush=True)

out = pp[["id", "homez"]].copy()
out["work_zone_new"] = out.id.map(assign).fillna(out.id.map(dict(zip(pp.id, pp.wz1)))).astype(float)
old = pd.read_csv(BG / "worker_workplace_zone_v1.csv") if (BG / "worker_workplace_zone_v1.csv").exists() else None
if old is not None:
    out = out.merge(old.rename(columns={"work_zone": "work_zone_old"})[["person_id", "work_zone_old"]],
                    left_on="id", right_on="person_id", how="left")
out.to_csv(BG / "worker_workplace_zone_v2.csv", index=False)
print("wrote worker_workplace_zone_v2.csv", flush=True)

# ---------- diagnostics: cross-harbor + commute time dist ----------
zx = dict(zip(zc.index, zc.coordX)); zy = dict(zip(zc.index, zc.coordY))
def side(z):   # crude harbor side test in the harbor band
    x, y = zx.get(z, 0), zy.get(z, 0)
    if not (165000 < y < 185000): return None
    return "E" if x > 437000 else "W"
h = out.dropna(subset=["work_zone_new"])
sides_h = h.homez.map(side); sides_w = h.work_zone_new.map(side)
cross = ((sides_h == "E") & (sides_w == "W")) | ((sides_h == "W") & (sides_w == "E"))
print(f"harbor-band cross-side commutes: {cross.sum():,} of {len(h):,} ({100*cross.mean():.1f}%)")
tmins = [Tz[hzi[r.homez], zi[int(r.work_zone_new)]] for r in h.sample(min(20000, len(h)), random_state=1).itertuples()]
print(f"commute network time: median {np.median(tmins):.1f} min, mean {np.mean(tmins):.1f} min")
