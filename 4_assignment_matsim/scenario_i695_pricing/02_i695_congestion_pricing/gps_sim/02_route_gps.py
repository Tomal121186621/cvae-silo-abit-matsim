#!/usr/bin/env python3
"""Step 2: route each GPS candidate O->D on the car network (free-flow shortest path,
scipy dijkstra), extract the I-95 portion, and emit (time, milepost, speed) trajectory
points. A trip 'uses I-95' if its route covers >=1 mi of the corridor over >=2 links."""
import numpy as np, pandas as pd, time
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

OUT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/network_validation_2023/FINAL_FIGURES/i95_gps_vs_model/cache"
MS2MPH = 2.2369363

net = np.load(f"{OUT}/net.npz", allow_pickle=True)
nx_, ny_ = net["nx"], net["ny"]
u, v, w, ln, free = net["u"], net["v"], net["w"], net["ln"], net["free"]
N = len(nx_)
G = csr_matrix((w, (u, v)), shape=(N, N))

# (from_node_idx, to_node_idx) -> edge row (keep min weight if parallel)
edge_of = {}
for i in range(len(u)):
    k = (int(u[i]), int(v[i]))
    if k not in edge_of or w[i] < w[edge_of[k]]:
        edge_of[k] = i

i95 = np.load(f"{OUT}/i95.npz", allow_pickle=True)
i95_edge = set(int(e) for e in i95["i95_edge"])
edge_mp = {int(e): float(m) for e, m in zip(i95["i95_edge"], i95["i95_edge_mp"])}

cand = pd.read_parquet(f"{OUT}/gps_candidates.parquet").reset_index(drop=True)
tree = cKDTree(np.column_stack([nx_, ny_]))
_, src = tree.query(np.column_stack([cand.ox.values, cand.oy.values]))
_, tgt = tree.query(np.column_stack([cand.dx.values, cand.dy.values]))
cand["src"] = src; cand["tgt"] = tgt
dep = cand.dep_sod.values

# group trips by source node
from collections import defaultdict
by_src = defaultdict(list)
for i in range(len(cand)):
    if src[i] != tgt[i]:
        by_src[int(src[i])].append(i)
usrcs = list(by_src.keys())
print(f"routing {len(cand)} trips from {len(usrcs)} unique source nodes...", flush=True)

rows = []          # trajectory points
used_trips = 0
t0 = time.time()
CHUNK = 300
for s0 in range(0, len(usrcs), CHUNK):
    chunk = usrcs[s0:s0 + CHUNK]
    dist, pred = dijkstra(G, indices=chunk, return_predecessors=True, min_only=False)
    for si, s in enumerate(chunk):
        pr = pred[si]
        for ti in by_src[s]:
            t = int(tgt[ti])
            if pr[t] < 0 and t != s:
                continue
            # reconstruct node path t -> s
            path = [t]; cur = t; ok = True; guard = 0
            while cur != s:
                cur = pr[cur]
                if cur < 0:
                    ok = False; break
                path.append(cur); guard += 1
                if guard > 100000:
                    ok = False; break
            if not ok:
                continue
            path.reverse()
            # walk edges, cumulative free-flow tt, collect I-95 segments
            ctime = dep[ti]
            seg = []          # (time_enter, mp, speed_mph, edge)
            i95_len = 0.0
            for a, b in zip(path[:-1], path[1:]):
                e = edge_of.get((a, b))
                if e is None:
                    continue
                tt = w[e]
                if e in i95_edge:
                    sp = free[e] * MS2MPH
                    seg.append((ctime, edge_mp[e], sp))
                    i95_len += ln[e]
                ctime += tt
            if len(seg) >= 2 and i95_len * 0.000621371 >= 1.0:
                used_trips += 1
                for k, (tm, mp, sp) in enumerate(seg):
                    rows.append((ti, k, tm, mp, sp))
    if (s0 // CHUNK) % 5 == 0:
        el = time.time() - t0
        print(f"  {s0+len(chunk)}/{len(usrcs)} srcs  used={used_trips}  {el:.0f}s", flush=True)

traj = pd.DataFrame(rows, columns=["trip", "seq", "time_sod", "milepost", "speed_mph"])
traj.to_parquet(f"{OUT}/gps_i95_traj.parquet")
print(f"DONE: {used_trips} GPS trips routed onto I-95 (>=1mi corridor). "
      f"{traj.trip.nunique()} unique, {len(traj)} points. {time.time()-t0:.0f}s", flush=True)
