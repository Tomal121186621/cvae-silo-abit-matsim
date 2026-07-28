#!/usr/bin/env python3
"""Baseline trip decomposition: internal (both ends in BMR) vs inflow (external anchor ->
interior) vs outflow (interior -> external anchor). External activities are anchored at the
131 cordon gateway crossings, so trip ends are classified by anchor-coordinate match.
Outputs: figV1_io_flows (daily totals + hourly tide) into trb_paper/figures/validation/.
"""
import gzip, re
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
PLANS = ROOT / "scenarios/01_base_no_pricing/output_calib_fs/pass7/output_plans.xml.gz"
ANCH = ROOT / "network_validation_2023/calibration/cordon_stations_expanded_anchored.csv"
OUT = ROOT / "trb_paper/figures/validation"; OUT.mkdir(parents=True, exist_ok=True)
SAMPLE = 10.0

a = pd.read_csv(ANCH)
anchors = {(round(x), round(y)) for x, y in zip(a.x, a.y)}

re_act = re.compile(r'<activity[^>]*type="([^"]+)"[^>]*x="([0-9.\-]+)" y="([0-9.\-]+)"'
                    r'(?:[^>]*end_time="(\d+):(\d+):\d+")?')
re_leg = re.compile(r'<leg mode="(\w+)"')
counts = {"internal": 0, "inflow": 0, "outflow": 0, "external-external": 0}
hourly = {"inflow": np.zeros(30), "outflow": np.zeros(30), "internal": np.zeros(30)}
in_sel, acts, legs = False, [], []

def is_anchor(x, y):
    return (round(float(x)), round(float(y))) in anchors

def flush(acts, legs):
    for i, mode in enumerate(legs):
        if i + 1 >= len(acts): break
        (t0, x0, y0, h0), (t1, x1, y1, _) = acts[i], acts[i + 1]
        o, d = is_anchor(x0, y0), is_anchor(x1, y1)
        k = ("external-external" if o and d else "inflow" if o else
             "outflow" if d else "internal")
        counts[k] += 1
        if k in hourly and h0 is not None and h0 < 30:
            hourly[k][h0] += 1

with gzip.open(PLANS, "rt") as f:
    for line in f:
        if "<plan" in line:
            in_sel = 'selected="yes"' in line; acts, legs = [], []
        elif "</plan>" in line and in_sel:
            flush(acts, legs); in_sel = False
        elif in_sel:
            m = re_act.search(line)
            if m:
                h = int(m.group(4)) if m.group(4) else None
                acts.append((m.group(1), m.group(2), m.group(3), h))
            else:
                m = re_leg.search(line)
                if m: legs.append(m.group(1))

tot = sum(counts.values())
print({k: f"{v*SAMPLE:,.0f} ({100*v/tot:.1f}%)" for k, v in counts.items()})

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
fig, a1 = plt.subplots(figsize=(3.4, 2.9))

cats = ["internal", "inflow", "outflow"]
tot = sum(counts[c] for c in cats)  # ext-ext excluded: same-gateway zero-length legs, no network load
C = {"internal": "#0072B2", "inflow": "#009E73", "outflow": "#D55E00", "external-external": "#999999"}
vals = [counts[c] * SAMPLE / 1e6 for c in cats]
bars = a1.bar(range(3), vals, 0.62, color=[C[c] for c in cats])
for b, c, v in zip(bars, cats, vals):
    a1.annotate(f"{v:.2f}M\n({100*counts[c]/tot:.1f}%)",
                (b.get_x() + b.get_width()/2, v), ha="center", va="bottom", fontsize=8)
a1.set_xticks(range(3)); a1.set_xticklabels(["internal", "inflow", "outflow"], fontsize=8)
a1.set_ylabel("daily person-trips (millions)")
a1.set_ylim(0, max(vals) * 1.22); a1.grid(axis="x", visible=False)
a1.set_title("Baseline daily trips: internal, inflow, and outflow", fontsize=9)

fig.savefig(OUT / "figV1_io_flows.pdf"); fig.savefig(OUT / "figV1_io_flows.png")
pd.DataFrame([{"category": k, "trips_x10": v * SAMPLE, "share_pct": 100*v/tot}
              for k, v in counts.items()]).to_csv(OUT / "io_flows.csv", index=False)
print("saved figV1_io_flows +", OUT / "io_flows.csv")
