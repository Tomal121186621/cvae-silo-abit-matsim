#!/usr/bin/env python3
"""Step 4: build our-model I-95 (time, milepost, speed) trajectories from the base_hybrid
events (via_i95 filtered copy), then draw the two-panel time-space comparison:
LEFT = GPS-derived (routed), RIGHT = ABIT/SILO model. Same axes, colored by speed."""
import gzip, os, re
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
import matplotlib.cm as cm

BASE = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
CACHE = f"{BASE}/network_validation_2023/FINAL_FIGURES/i95_gps_vs_model/cache"
EVENTS = f"{BASE}/scenarios/02_i695_congestion_pricing/via_i95/i95_events.xml.gz"
FIG_MAIN = f"{BASE}/network_validation_2023/FINAL_FIGURES/i95_gps_vs_model"
FIG_GPS = f"{BASE}/scenarios/02_i695_congestion_pricing/gps_sim/figures"
MS2MPH = 2.2369363

# ---- caches ----
net = np.load(f"{CACHE}/net.npz", allow_pickle=True)
lid_arr = net["lid"]; ln = net["ln"]
len_of = {str(l): float(x) for l, x in zip(lid_arr, ln)}
i95 = np.load(f"{CACHE}/i95.npz", allow_pickle=True)
mp_of = {str(l): float(m) for l, m in zip(i95["i95_lids"], i95["i95_mp"])}
dir_of = {str(l): str(d) for l, d in zip(i95["i95_lids"], i95["i95_dir"])}
i95_links = set(mp_of.keys())

# ---- parse our-model events into per-vehicle I-95 trajectories ----
print("parsing model events...", flush=True)
enter = {}   # (veh,link) -> enter_time  (current open)
veh_pts = {} # veh -> list of (t_enter, milepost, speed_mph, dir)
rx = re.compile(r'time="([\d.]+)" type="([^"]+)" link="([^"]+)" vehicle="([^"]+)"')
n = 0
for line in gzip.open(EVENTS, "rt"):
    m = rx.search(line)
    if not m:
        continue
    t, typ, link, veh = float(m.group(1)), m.group(2), m.group(3), m.group(4)
    if link not in i95_links:
        continue
    if typ == "entered link":
        enter[(veh, link)] = t
    elif typ == "left link":
        te = enter.pop((veh, link), None)
        if te is None:
            continue
        dt = t - te
        sp = (len_of.get(link, 0.0) / dt * MS2MPH) if dt > 0 else np.nan
        veh_pts.setdefault(veh, []).append((te, mp_of[link], sp, dir_of[link]))
    n += 1
print(f"  {n} I-95 movement events, {len(veh_pts)} vehicles on corridor", flush=True)

# ---- load GPS routed trajectories ----
gps = pd.read_parquet(f"{CACHE}/gps_i95_traj.parquet")
print(f"  GPS routed I-95 trips: {gps.trip.nunique()}, points {len(gps)}", flush=True)

# ---- plotting helpers ----
T0, T1 = 5 * 3600, 22 * 3600
norm = Normalize(vmin=0, vmax=70)
cmap = cm.get_cmap("RdYlGn")

def model_segments():
    segs, cols = [], []
    for veh, pts in veh_pts.items():
        pts = sorted(pts)
        if len(pts) < 2:
            continue
        for (t0, m0, s0, d0), (t1, m1, s1, d1) in zip(pts[:-1], pts[1:]):
            if t1 - t0 > 900:      # break trajectory across large gaps (>15min)
                continue
            segs.append([(t0 / 3600, m0), (t1 / 3600, m1)])
            cols.append(0.5 * (np.nan_to_num(s0, nan=35) + np.nan_to_num(s1, nan=35)))
    return segs, cols

def gps_segments():
    segs, cols = [], []
    for tid, g in gps.groupby("trip"):
        g = g.sort_values("time_sod")
        tv = g.time_sod.values; mv = g.milepost.values; sv = g.speed_mph.values
        for i in range(len(g) - 1):
            if tv[i+1] - tv[i] > 900:
                continue
            segs.append([(tv[i] / 3600, mv[i]), (tv[i+1] / 3600, mv[i+1])])
            cols.append(0.5 * (sv[i] + sv[i+1]))
    return segs, cols

print("building segments...", flush=True)
gseg, gcol = gps_segments()
mseg, mcol = model_segments()
print(f"  GPS segs {len(gseg)}, model segs {len(mseg)}", flush=True)

fig, axes = plt.subplots(1, 2, figsize=(17, 9), sharey=True)
for ax, (segs, cols, title, sub) in zip(axes, [
    (gseg, gcol, "GPS-derived (routed)", f"{gps.trip.nunique():,} device trips routed onto I-95"),
    (mseg, mcol, "ABIT / SILO model", f"{len(veh_pts):,} resident vehicles on I-95")]):
    lc = LineCollection(segs, cmap=cmap, norm=norm, linewidths=0.35, alpha=0.5)
    lc.set_array(np.array(cols))
    ax.add_collection(lc)
    ax.set_xlim(5, 22); ax.set_ylim(0, 55)
    ax.set_xlabel("time of day (h)")
    ax.set_title(f"{title}\n{sub}", fontsize=12)
    ax.set_xticks(range(5, 23, 2))
    ax.grid(alpha=0.2, lw=0.4)
axes[0].set_ylabel("I-95 milepost  (0 = Washington DC end  →  ~54 = Delaware line)")
sm = cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
cb = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02)
cb.set_label("link speed (mph)")
fig.suptitle("I-95 Trajectories: GPS-derived vs ABIT/SILO model (Base 2023)",
             fontsize=15, weight="bold", y=0.99)
cap = ("Time–space diagrams of the I-95 corridor (Washington DC ↔ Delaware line). "
       "LEFT: WMA device (GPS/MDLD) trips, mode 0 (car); O–D endpoints only, so the I-95 "
       "route/times are INFERRED by free-flow shortest-path routing on the MATSim network "
       "(no waypoints) — a device SAMPLE, not expanded, WMA/DC-centric coverage, so northern "
       "MD volumes thin out. RIGHT: our ABIT/SILO base run — resident trips only "
       "(I-95 through/external traffic not modeled), so the corridor is under-loaded and near "
       "free-flow. Network: output_base/base_hybrid (a corrected base_speedfix network is still "
       "running and not used here). This is a trajectory VISUAL comparison, not a calibrated "
       "volume study.")
fig.text(0.5, 0.015, cap, ha="center", va="bottom", fontsize=8.2, wrap=True,
         bbox=dict(boxstyle="round", fc="#f4f4f4", ec="#cccccc"))
fig.subplots_adjust(left=0.06, right=0.9, top=0.9, bottom=0.16, wspace=0.05)

os.makedirs(FIG_GPS, exist_ok=True)
for d in (FIG_MAIN, FIG_GPS):
    p = f"{d}/i95_gps_vs_model_timespace.png"
    fig.savefig(p, dpi=150)
    print("wrote", p, flush=True)
