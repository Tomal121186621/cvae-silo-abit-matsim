#!/usr/bin/env python3
"""ABIT (activity-based, calib5-2023) vs trip-based MITO comparator vs RTS observed.

Panels:
  (a) trip-length distribution (all purposes): RTS observed vs ABIT vs trip-based MITO
  (b) trips-per-tour distribution: RTS vs ABIT — with the trip-based comparator shown
      at its structural value (every "tour" is a single unlinked trip by construction)
  (c) tours per mobile person-day: RTS vs ABIT (+ trip-based structural line)

Data:
  RTS   : ABIT/input/rts/rts_trips_clean.csv (+ rts_tours.csv), weighted (wttrdfin)
  ABIT  : ABIT/input/maryland/output/legs_full.csv (chunked sample)
  MITO  : Updated MATSim/input/population/bmr_plans_p05.xml.gz (one agent per MITO trip)
Distances: beeline from coordinates for ABIT & MITO; RTS uses its reported network
distance scaled by 1/1.3 route factor to beeline-equivalent (noted in caption).
"""
import gzip, re, json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
HERE = ROOT / "MITO-comparison"; (HERE / "outputs").mkdir(parents=True, exist_ok=True)
RTS_TRIPS = ROOT / "ABIT/input/rts/rts_trips_clean.csv"
RTS_TOURS = ROOT / "ABIT/input/rts/rts_tours.csv"
ABIT_LEGS = ROOT / "ABIT/input/maryland/output/legs_full.csv"
MITO_PLANS = ROOT / "Updated MATSim/input/population/bmr_plans_p05.xml.gz"
ROUTE_FACTOR = 1.3

# ---------- RTS ----------
rt = pd.read_csv(RTS_TRIPS, low_memory=False)
rt = rt[(rt.get("o_bmc_taz", 1) > 0)]
w = rt["wttrdfin"].to_numpy(float) if "wttrdfin" in rt.columns else np.ones(len(rt))
rts_km = pd.to_numeric(rt["distance"], errors="coerce").to_numpy(float) * 1.60934 / ROUTE_FACTOR
ok = np.isfinite(rts_km) & (rts_km > 0.1) & (rts_km < 150)
rts_km, rts_w = rts_km[ok], w[ok]
tours = pd.read_csv(RTS_TOURS, low_memory=False)
tw = tours["wtperfin"].to_numpy(float) if "wtperfin" in tours.columns else np.ones(len(tours))
rts_tpt = tours["n_trips"].to_numpy(float)
per = tours.groupby("person_id").agg(n_tours=("anchor", "size"), w=("wtperfin", "first"))
print(f"RTS: {len(rts_km):,} trips, {len(tours):,} tours, {len(per):,} persons")

# ---------- ABIT legs (chunked sample) ----------
ab = []
for ch in pd.read_csv(ABIT_LEGS, chunksize=2_000_000,
                      usecols=["person_id", "previous_purpose", "next_purpose",
                               "start_time_min", "start_x", "start_y", "end_x", "end_y"]):
    ch = ch[pd.to_numeric(ch.person_id, errors="coerce").fillna(0).astype(np.int64) % 7 == 0]
    ch = ch[(ch.start_time_min // 1440) == 2]     # one representative WEEKDAY (legs_full spans a week)
    ab.append(ch)
ab = pd.concat(ab, ignore_index=True)
ab_km = np.hypot(ab.end_x - ab.start_x, ab.end_y - ab.start_y).to_numpy() / 1000.0
ok = np.isfinite(ab_km) & (ab_km > 0.1) & (ab_km < 150)
ab_km = ab_km[ok]
# tours: split each person's leg sequence at returns to home
abt = ab.sort_index().groupby("person_id")
tpt, tours_pp = [], []
for pid, g in abt:
    n_tours, n_in_tour = 0, 0
    for np_ in g.next_purpose:
        n_in_tour += 1
        if str(np_).lower().startswith("home"):
            tpt.append(n_in_tour); n_tours += 1; n_in_tour = 0
    if n_tours > 0: tours_pp.append(n_tours)
ab_tpt = np.array(tpt, float); ab_tourspp = np.array(tours_pp, float)
print(f"ABIT: {len(ab_km):,} legs sampled, {len(ab_tpt):,} tours, {len(ab_tourspp):,} persons")

# ---------- trip-based MITO plans (one agent = one trip) ----------
mito_km = []
re_act = re.compile(r'<act(?:ivity)? [^>]*x="([0-9.\-]+)" y="([0-9.\-]+)"')
with gzip.open(MITO_PLANS, "rt") as f:
    prev = None
    for line in f:
        if "<person" in line: prev = None; continue
        m = re_act.search(line)
        if m:
            xy = (float(m.group(1)), float(m.group(2)))
            if prev is not None:
                d = np.hypot(xy[0]-prev[0], xy[1]-prev[1]) / 1000.0
                if 0.1 < d < 150: mito_km.append(d)
            prev = xy
mito_km = np.array(mito_km)
print(f"trip-based MITO: {len(mito_km):,} trips")

# ---------- figure ----------
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
OBS, TB, AB_C = "#555555", "#E69F00", "#0072B2"
fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7), gridspec_kw={"wspace": 0.4})

# (a) trip length CDF
ax = axs[0]
xs = np.linspace(0, 60, 200)
def wcdf(v, w=None):
    w = np.ones(len(v)) if w is None else w
    o = np.argsort(v); v, w = v[o], w[o]
    c = np.cumsum(w) / w.sum()
    return np.interp(xs, v, c)
ax.plot(xs, wcdf(rts_km, rts_w), color=OBS, lw=1.8, ls="--", label="RTS observed")
ax.plot(xs, wcdf(ab_km), color=AB_C, lw=1.6, label="ABIT (activity-based)")
ax.plot(xs, wcdf(mito_km), color=TB, lw=1.6, label="Trip-based (MITO)")
ax.set_xlabel("trip length, beeline km"); ax.set_ylabel("cumulative share")
ax.set_title("(a) Trip-length distribution", fontsize=9)
ax.legend(frameon=False, fontsize=7)
for nm, v, ww in (("RTS", rts_km, rts_w), ("ABIT", ab_km, None), ("MITO", mito_km, None)):
    o = np.argsort(v); vv = v[o]; www = (np.ones(len(v)) if ww is None else ww[o])
    med = vv[np.searchsorted(np.cumsum(www)/www.sum(), 0.5)]
    print(f"median trip km {nm}: {med:.1f}")

# (b) trips per tour — horizontal, trip-based shown as data (100% single-trip)
ax = axs[1]
ks = np.arange(1, 8)
rts_h = np.array([(tw[rts_tpt == k]).sum() for k in ks]); rts_h = rts_h / rts_h.sum()
ab_h = np.array([(ab_tpt == k).sum() for k in ks], float); ab_h = ab_h / ab_h.sum()
tb_h = np.zeros(len(ks)); tb_h[0] = 1.0
yy = np.arange(len(ks)); hh_ = 0.27
ax.barh(yy - hh_, 100*rts_h, hh_, color=OBS, label="RTS observed")
ax.barh(yy, 100*ab_h, hh_, color=AB_C, label="ABIT")
ax.barh(yy + hh_, 100*tb_h, hh_, color=TB, label="Trip-based (structural)")
ax.text(100, 0 + hh_, " 100%", va="center", fontsize=7.5, color="#8a5a00", weight="bold")
ax.set_yticks(yy); ax.set_yticklabels([str(k) if k < 7 else "7+" for k in ks], fontsize=8)
ax.invert_yaxis()
ax.set_ylabel("trips per home-based tour"); ax.set_xlabel("share of tours (%)")
ax.set_xlim(0, 118)
ax.set_title("(b) Tour complexity", fontsize=9)
ax.legend(frameon=False, fontsize=6.6, loc="lower right")

# (c) tours per mobile person-day — horizontal
ax = axs[2]
ks2 = np.arange(1, 6)
rts_t = np.array([(per.w[per.n_tours == k]).sum() for k in ks2]); rts_t = rts_t / rts_t.sum()
ab_t = np.array([(ab_tourspp == k).sum() for k in ks2], float); ab_t = ab_t / ab_t.sum()
yy2 = np.arange(len(ks2)); hh2 = 0.36
ax.barh(yy2 - hh2/2, 100*rts_t, hh2, color=OBS, label="RTS observed")
ax.barh(yy2 + hh2/2, 100*ab_t, hh2, color=AB_C, label="ABIT")
ax.set_yticks(yy2); ax.set_yticklabels([str(k) if k < 5 else "5+" for k in ks2], fontsize=8)
ax.invert_yaxis()
ax.set_ylabel("tours per mobile person"); ax.set_xlabel("share of persons (%)")
ax.set_title("(c) Daily tour frequency", fontsize=9)
ax.legend(frameon=False, fontsize=7)

fig.savefig(HERE / "outputs/fig_abit_vs_tripbased.pdf")
fig.savefig(HERE / "outputs/fig_abit_vs_tripbased.png")
json.dump({"rts_trips": int(len(rts_km)), "abit_legs_sampled": int(len(ab_km)),
           "mito_trips": int(len(mito_km)),
           "median_km": {"rts": float(np.median(rts_km)), "abit": float(np.median(ab_km)),
                          "mito": float(np.median(mito_km))},
           "trips_per_tour_mean": {"rts": float((rts_tpt*tw).sum()/tw.sum()),
                                    "abit": float(ab_tpt.mean()), "tripbased": 1.0}},
          open(HERE / "outputs/abit_vs_tripbased_stats.json", "w"), indent=1)
print("wrote fig_abit_vs_tripbased + stats")
