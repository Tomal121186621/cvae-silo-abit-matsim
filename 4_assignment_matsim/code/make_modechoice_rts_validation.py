#!/usr/bin/env python3
"""Publication-quality (TRB) validation of the MATSim SubtourModeChoice model against the
Maryland RTS household travel survey.

Three-way comparison on the common 5-mode universe (car / ride / pt / walk / bike):
  RTS survey (weighted, BMR-resident trips)  vs  ABIT demand (input plans)  vs  MATSim (converged run)
Figures:
  figM1_mode_shares      grouped bars, all three sources + NTD-implied transit marker
  figM2_mode_by_distance car/ride/walk+bike/pt shares by trip-distance band, RTS vs MATSim
  mode_validation_rts.csv underlying numbers
Usage: make_modechoice_rts_validation.py <matsim_run_dir> <abit_population.xml.gz> <out_dir>
"""
import sys, os, gzip
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN, ABITPOP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
RTS = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/ABIT/input/rts/rts_trips_clean.csv"
BMR = {'24003','24005','24013','24025','24027','24510'}
MODES = ["car", "ride", "pt", "walk", "bike"]
LBL = {"car":"Car (driver)", "ride":"Car (passenger)", "pt":"Transit", "walk":"Walk", "bike":"Bike"}
COL = {"MWCOG RHTS 2017-18":"0.55", "ABIT":"#0072B2", "MATSim":"#D55E00"}
NTD_TRANSIT = 0.021   # NTD-2023-implied transit trip share (RTS over-reports transit ~10%; see ABIT docs)
plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":9,"axes.labelsize":9,"axes.titlesize":9,
    "xtick.labelsize":8,"ytick.labelsize":8,"legend.fontsize":7.5,
    "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":0.8})
def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    plt.close(fig); print(f"  saved {name}")

BANDS = [(0,1),(1,2),(2,5),(5,10),(10,20),(20,200)]
BLAB = ["<1","1-2","2-5","5-10","10-20","20+"]

def modecat(code):
    try: c = int(float(code))
    except: return None
    if c in (4,3): return "car"
    if c in (5,11,12): return "ride"
    if c in (7,8,9,10): return "pt"
    if c == 1: return "walk"
    if c == 2: return "bike"
    return None                      # school bus / air / water / other: outside the modeled universe

# ---------- RTS ----------
rts = pd.read_csv(RTS, low_memory=False)
# BMR filter: trips originating in a Baltimore Metropolitan Council zone (o_bmc_taz > 0)
rts = rts[pd.to_numeric(rts.o_bmc_taz, errors="coerce") > 0].copy()
# universe alignment with the modeled population (documented in methods; label stays clean):
rts = rts[(pd.to_numeric(rts.age, errors="coerce") >= 19) &
          (pd.to_numeric(rts.student_status, errors="coerce").fillna(0) <= 0)].copy()
rts["m"] = rts.travel_mode.map(modecat)
rts = rts[rts.m.notna() & (pd.to_numeric(rts.wttrdfin, errors="coerce") > 0)].copy()
rts["w"] = pd.to_numeric(rts.wttrdfin, errors="coerce")
rts["dist"] = pd.to_numeric(rts.distance, errors="coerce")
rts_sh = rts.groupby("m").w.sum(); rts_sh = rts_sh/rts_sh.sum()

def leg_share_and_dist(popfile, selected_only=True):
    sh = {m:0 for m in MODES}; bd = {m:np.zeros(len(BANDS)) for m in MODES}
    for _, el in ET.iterparse(gzip.open(popfile,"rb"), events=("end",)):
        if el.tag != "person": continue
        plans = el.findall("plan")
        plan = next((p for p in plans if p.get("selected")=="yes"), plans[0] if plans else None)
        if plan is not None:
            # TRIP-level main mode: legs between REAL activities ("pt interaction" stages folded in;
            # transit access/egress walks are NOT walk trips). Main mode: pt > car > ride > bike > walk.
            items = [e for e in plan]
            trip_modes, trip_ends = [], []
            cur_modes, o = [], None
            for e in items:
                if e.tag == "activity":
                    if e.get("type") == "pt interaction": continue
                    if o is not None and cur_modes:
                        trip_modes.append(cur_modes); trip_ends.append((o, e)); cur_modes = []
                    o = e
                elif e.tag == "leg":
                    cur_modes.append(e.get("mode").replace("transit_walk","walk").replace("access_walk","walk").replace("egress_walk","walk"))
            RANK = ["pt","car","ride","bike","walk"]
            for ms, (oa, da) in zip(trip_modes, trip_ends):
                m = next((r for r in RANK if r in ms), None)
                if m is None or m not in sh: continue
                sh[m] += 1
                x1,y1 = float(oa.get("x")), float(oa.get("y"))
                x2,y2 = float(da.get("x")), float(da.get("y"))
                dmi = np.hypot(x2-x1, y2-y1)*1.3/1609.34
                for b,(lo,hi) in enumerate(BANDS):
                    if lo <= dmi < hi: bd[m][b] += 1; break
        el.clear()
    tot = sum(sh.values())
    return {m: sh[m]/tot for m in MODES}, bd

print("parsing ABIT demand plans...")
abit_sh, abit_bd = leg_share_and_dist(ABITPOP)
print("parsing MATSim converged plans...")
mats_pop = os.path.join(RUN, "output_plans.xml.gz")
mats_sh, mats_bd = leg_share_and_dist(mats_pop)

# ---------- figM1: overall shares ----------
srcs = {"MWCOG RHTS 2017-18": {m: float(rts_sh.get(m,0)) for m in MODES},
        "ABIT": abit_sh, "MATSim": mats_sh}
x = np.arange(len(MODES)); w = 0.26
fig, ax = plt.subplots(figsize=(5.2, 3.4))
for k,(name, sh) in enumerate(srcs.items()):
    ax.bar(x+(k-1)*w, [100*sh[m] for m in MODES], w, color=COL[name], label=name)
ax.plot([2-1.6*w, 2+1.6*w], [2.1]*2, "k--", lw=1.0, label="NTD 2023 (counted ridership)")
ax.set_xticks(x); ax.set_xticklabels([LBL[m] for m in MODES], fontsize=8)
ax.set_ylabel("Share of trips (%)")
ax.legend(frameon=False)
for k,(name, sh) in enumerate(srcs.items()):
    for i,m in enumerate(MODES):
        ax.text(i+(k-1)*w, 100*sh[m]+0.7, f"{100*sh[m]:.1f}", ha="center", fontsize=6.5)
ax.set_ylim(0, 88)
save(fig, "figM1_mode_shares")

# ---------- figM2: mode share by distance band ----------
rts["band"] = pd.cut(rts.dist, [b[0] for b in BANDS]+[200], labels=BLAB, right=False)
rts_band = rts.pivot_table(index="band", columns="m", values="w", aggfunc="sum", observed=True).fillna(0)
rts_band = rts_band.div(rts_band.sum(axis=1), axis=0)
fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.1), sharey=True)
groups = {"Car (driver)":["car"], "Car (passenger)":["ride"], "Walk + bike":["walk","bike"], "Transit":["pt"]}
GC = {"Car (driver)":"#D55E00","Car (passenger)":"#E69F00","Walk + bike":"#009E73","Transit":"#0072B2"}
for ax, (name, bd, tag) in zip(axs, [("MWCOG RHTS 2017-18", None, "rts"), ("MATSim", mats_bd, "matsim")]):
    for glab, ms in groups.items():
        if tag == "rts":
            y = [100*sum(rts_band.loc[b, m] if m in rts_band.columns else 0 for m in ms) for b in BLAB]
        else:
            tot = sum(bd[m] for m in MODES); tot[tot==0] = 1
            y = [100*sum(bd[m][i] for m in ms)/tot[i] for i in range(len(BANDS))]
        ax.plot(range(len(BLAB)), y, "-o", ms=3, lw=1.4, color=GC[glab], label=glab)
    ax.set_xticks(range(len(BLAB))); ax.set_xticklabels(BLAB, fontsize=8)
    ax.set_xlabel("Trip distance (miles)"); ax.set_title(name)
axs[0].set_ylabel("Share of trips in band (%)"); axs[0].legend(frameon=False, fontsize=7)
save(fig, "figM2_mode_by_distance")

# ---------- CSV ----------
rows = []
for m in MODES:
    rows.append(dict(mode=m, rts=float(rts_sh.get(m,0)), abit=abit_sh[m], matsim=mats_sh[m],
                     matsim_minus_rts_pp=100*(mats_sh[m]-float(rts_sh.get(m,0))),
                     matsim_minus_abit_pp=100*(mats_sh[m]-abit_sh[m])))
pd.DataFrame(rows).to_csv(f"{OUT}/mode_validation_rts.csv", index=False)
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
