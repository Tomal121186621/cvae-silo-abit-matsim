#!/usr/bin/env python3
"""Mode share by TRIP PURPOSE: MWCOG RHTS 2017-18 vs ABIT vs MATSim (TRB publication style).

Purposes harmonized to the model's activity universe (work / shopping / other, home-based or not):
  HBW  home-based work        HBS  home-based shopping
  HBO  home-based other       NHB  non-home-based
RHTS side: BMR-origin trips, universe-aligned (adults, non-students), weighted; SCHOOL trips excluded
(education is outside the modeled universe). Model side: trip-level main modes between real activities.

Usage: make_mode_by_purpose.py <matsim_run_dir> <abit_population.xml.gz> <out_dir>
"""
import sys, os, gzip
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN, ABITPOP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
RTS = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/ABIT/input/rts/rts_trips_clean.csv"
MODES = ["car", "ride", "pt", "walk", "bike"]
LBL = {"car":"Car (driver)","ride":"Car (pass.)","pt":"Transit","walk":"Walk","bike":"Bike"}
PURPS = ["HBW", "HBS", "HBO", "NHB"]
PLBL = {"HBW":"Home-based work","HBS":"Home-based shopping","HBO":"Home-based other","NHB":"Non-home-based"}
COL = {"MWCOG RHTS 2017-18":"0.55","ABIT":"#0072B2","MATSim":"#D55E00"}
plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":9,"axes.labelsize":9,"axes.titlesize":9,
    "xtick.labelsize":8,"ytick.labelsize":8,"legend.fontsize":7.5,
    "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":0.8})

def endcat_rts(code):
    try: c = int(float(code))
    except: return "OTHER"
    return {1:"HOME",2:"WORK",4:"SCHOOL",5:"SHOP"}.get(c,"OTHER")
def purpose(o_end, d_end):
    if o_end == "HOME":
        return {"WORK":"HBW","SHOP":"HBS"}.get(d_end,"HBO") if d_end != "HOME" else "HBO"
    if d_end == "HOME":
        return {"WORK":"HBW","SHOP":"HBS"}.get(o_end,"HBO")
    return "NHB"
def modecat(code):
    try: c = int(float(code))
    except: return None
    return {4:"car",3:"car",5:"ride",11:"ride",12:"ride",7:"pt",8:"pt",9:"pt",10:"pt",1:"walk",2:"bike"}.get(c)

# ---------- RHTS ----------
rts = pd.read_csv(RTS, low_memory=False)
rts = rts[pd.to_numeric(rts.o_bmc_taz, errors="coerce") > 0]
rts = rts[(pd.to_numeric(rts.age, errors="coerce") >= 19) &
          (pd.to_numeric(rts.student_status, errors="coerce").fillna(0) <= 0)].copy()
rts["m"] = rts.travel_mode.map(modecat)
rts["oe"] = rts.o_activity.map(endcat_rts); rts["de"] = rts.d_activity.map(endcat_rts)
rts = rts[(rts.oe != "SCHOOL") & (rts.de != "SCHOOL")]
rts["purp"] = [purpose(o,d) for o,d in zip(rts.oe, rts.de)]
rts = rts[rts.m.notna() & (pd.to_numeric(rts.wttrdfin, errors="coerce") > 0)].copy()
rts["w"] = pd.to_numeric(rts.wttrdfin, errors="coerce")
rts_pm = rts.pivot_table(index="purp", columns="m", values="w", aggfunc="sum").fillna(0)
rts_pm = rts_pm.div(rts_pm.sum(axis=1), axis=0)

# ---------- model plans: trips with purpose (dest activity type; home-based from origin/dest) ----------
def trips_by_purpose(popfile):
    pm = {p:{m:0 for m in MODES} for p in PURPS}
    def act_end(t):
        return {"home":"HOME","work":"WORK","shopping":"SHOP"}.get(t,"OTHER")
    for _, el in ET.iterparse(gzip.open(popfile,"rb"), events=("end",)):
        if el.tag != "person": continue
        plans = el.findall("plan")
        plan = next((p for p in plans if p.get("selected")=="yes"), plans[0] if plans else None)
        if plan is not None:
            trip_modes, ends = [], []
            cur, o = [], None
            for e in plan:
                if e.tag == "activity":
                    if e.get("type") == "pt interaction": continue
                    if o is not None and cur:
                        trip_modes.append(cur); ends.append((act_end(o.get("type")), act_end(e.get("type")))); cur = []
                    o = e
                elif e.tag == "leg":
                    cur.append(e.get("mode").replace("transit_walk","walk"))
            RANK = ["pt","car","ride","bike","walk"]
            for ms,(oe,de) in zip(trip_modes, ends):
                m = next((r for r in RANK if r in ms), None)
                if m is None or m not in MODES: continue
                pm[purpose(oe,de)][m] += 1
        el.clear()
    out = pd.DataFrame(pm).T[MODES]
    return out.div(out.sum(axis=1), axis=0)

print("parsing ABIT plans..."); abit_pm = trips_by_purpose(ABITPOP)
print("parsing MATSim plans..."); mats_pm = trips_by_purpose(os.path.join(RUN, "output_plans.xml.gz"))

# ---------- figure: 2x2 purpose panels ----------
fig, axs = plt.subplots(2, 2, figsize=(7.0, 5.6), sharey=True)
x = np.arange(len(MODES)); w = 0.26
for ax, p in zip(axs.flat, PURPS):
    srcs = {"MWCOG RHTS 2017-18": [100*rts_pm.loc[p].get(m,0) if p in rts_pm.index else 0 for m in MODES],
            "ABIT":  [100*abit_pm.loc[p,m] for m in MODES],
            "MATSim":[100*mats_pm.loc[p,m] for m in MODES]}
    for k,(name,vals) in enumerate(srcs.items()):
        ax.bar(x+(k-1)*w, vals, w, color=COL[name], label=name if p=="HBW" else None)
        for xi,v in zip(x,vals):
            if v >= 3: ax.text(xi+(k-1)*w, v+1.0, f"{v:.0f}", ha="center", fontsize=6)
    ax.set_title(PLBL[p]); ax.set_xticks(x)
    ax.set_xticklabels([LBL[m] for m in MODES], fontsize=7)
    ax.set_ylim(0, 100)
for ax in axs[:,0]: ax.set_ylabel("Share of trips (%)")
axs[0,0].legend(frameon=False, fontsize=7.5, loc="upper right")
fig.tight_layout()
fig.savefig(f"{OUT}/figM3_mode_by_purpose.png", dpi=600, bbox_inches="tight")
fig.savefig(f"{OUT}/figM3_mode_by_purpose.pdf", bbox_inches="tight")
print("  saved figM3_mode_by_purpose")

# ---------- CSV ----------
rows=[]
for p in PURPS:
    for m in MODES:
        rows.append(dict(purpose=p, mode=m,
                         rhts=float(rts_pm.loc[p].get(m,0)) if p in rts_pm.index else 0.0,
                         abit=float(abit_pm.loc[p,m]), matsim=float(mats_pm.loc[p,m])))
df=pd.DataFrame(rows); df.to_csv(f"{OUT}/mode_by_purpose.csv", index=False)
piv=df.pivot_table(index="purpose",columns="mode")
print((100*piv).round(1).to_string())
