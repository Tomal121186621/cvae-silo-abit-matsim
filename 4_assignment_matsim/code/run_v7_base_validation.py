#!/usr/bin/env python3
"""v7 base AADT-2023 road validation driver.

Reuses the EXISTING validation infra (validate_base_hybrid + netval2023_common)
pointed at the COMPLETED v7 base run:
  scenarios/02_i695_congestion_pricing/output_base/base_calibrated  (it.64)

Writes into network_validation_2023/v7_base/:
  per_facility_table.csv, per_facility_table_clean.csv,
  figA_scatter_by_facility.{png,pdf}, figB_geh_by_facility.{png,pdf},
  figC_relbias_by_facility.{png,pdf}, screenline_hybrid.csv,
  summary.csv (combined per-facility + per-interstate), HEADLINE.txt

Per-interstate panels + route_validation_summary.csv are produced by the sibling
make_aadt_route_figures_v7.py into v7_base/aadt_validation_by_route/.

Demand is a 10% sample -> sim volumes scaled x10 (SAMPLE_SCALE, flowCapacityFactor 0.1),
identical to the existing scripts. Speed/transit gate steps are NOT run (this is the
AADT road validation only, per task).
"""
import os, sys
from pathlib import Path

# --- point the shared infra at the v7 base run BEFORE importing anything from it
os.environ["NETVAL_OUTDIR"] = "scenarios/02_i695_congestion_pricing/output_base/base_calibrated"
os.environ["NETVAL_ITER"]   = "64"
os.environ["NETVAL_SUB"]    = "v7_base"
CODE = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/code")
sys.path.insert(0, str(CODE))

import numpy as np, pandas as pd
import validate_base_hybrid as vbh   # setdefault() in it respects our env above

ROOT   = vbh.ROOT
OUTDIR = vbh.OUTDIR
print("run under validation:", os.environ["NETVAL_OUTDIR"])
print("linkstats:", vbh.LINKSTATS, "exists=", vbh.LINKSTATS.exists())
assert vbh.LINKSTATS.exists(), "v7 linkstats missing -- wrong run?"

# ---------------------------------------------------------------- per-facility
ls = vbh.load_linkstats()
i695_ids = set(x for x in (ROOT/"scenarios/toll_research/i695_link_ids.txt").read_text().splitlines()
               if x and not x.startswith("#"))
df, tab_raw, tab_clean, drop = vbh.counts(ls)
vbh.fig_counts(df, i695_ids)
scr_pct = vbh.screenline(df)

# ---------------------------------------------------------------- combined summary.csv
# per-facility (cleaned) rows
fac = tab_clean.copy()
fac.insert(0, "level", "facility")
fac = fac.rename(columns={"facility": "group"})

# the route script's enriched summary carries three blocks via its own `level` column:
#   speed_tier | facility_tier | route  (+ speed_band/mean_mph for the speed block)
route_csv = OUTDIR/"aadt_validation_by_route/route_validation_summary.csv"
frames = [fac]
if route_csv.exists():
    r = pd.read_csv(route_csv)
    keep = ["level","route","speed_band","mean_mph","facility","n","corr2","GEH_lt5_pct",
            "pctRMSE","median_bias_pct","median_ratio","within_facband_pct"]
    r = r[[c for c in keep if c in r.columns]].rename(columns={
        "route":"group","GEH_lt5_pct":"pctGEH5","pctRMSE":"rmse_pct",
        "median_bias_pct":"medbias","median_ratio":"sim_div_obs","within_facband_pct":"within_band_pct"})
    frames.append(r)
summary = pd.concat(frames, ignore_index=True)
# tidy column order: level first, then group/labels, then metrics
front = [c for c in ["level","group","speed_band","mean_mph","facility","n"] if c in summary.columns]
summary = summary[front + [c for c in summary.columns if c not in front]]
summary.to_csv(OUTDIR/"summary.csv", index=False)
print("\nwrote", OUTDIR/"summary.csv", "(blocks:", ", ".join(sorted(summary.level.dropna().unique())), ")")

# ---------------------------------------------------------------- headline
# Lead with the DAILY-appropriate lens (facility-band pass rate + median bias + GEH<5), NOT the pooled
# corr² (a pooling artifact: every sub-class corr² is 0.42-0.62; true R² is NEGATIVE for freeways).
rv = pd.read_csv(route_csv)
ftier = rv[rv.level=="facility_tier"].set_index("route") if "level" in rv.columns else pd.DataFrame()
allm_n = int(tab_clean.set_index("facility").loc["ALL (mainline)"].n)  # cleaned mainline n plotted in figA/B/C
H = []
H.append("v7 BASE AADT-2023 ROAD DIAGNOSTIC  (run: base_calibrated, it.64, resident-only demand, sim x10)")
H.append("="*88)
H.append("HEADLINE OBSERVED TARGET = passenger-car AADT: freight/bus removed from the observed count via MDOT")
H.append("2023 vehicle-class shares WHERE AVAILABLE (~20% of stations, ~761 of 3795); a facility-median fallback")
H.append("(median deduction ~3.4%) is used for the other ~80%. This is NOT a per-station decomposition. The")
H.append("auto-only resident demand is comparable only to auto counts. (Total-AADT variant lives in */total_aadt/.)")
H.append("")
H.append("Primary metrics are the DAILY lens: NCHRP ±facility-band pass rate, median bias, sim/obs ratio.")
H.append("corr² = squared Pearson r (STRUCTURE only, blind to level bias); true R² = 1-SSE/SST shown beside")
H.append("it and is NEGATIVE where the resident-only level deficit is large (freeways). GEH<5 is a strict")
H.append("HOURLY threshold applied here to DAILY AADT, so low GEH<5 shares are EXPECTED — the ±band + bias")
H.append("are the appropriate daily lens; GEH is reported for completeness only.")
H.append("")
H.append("STATION DENOMINATOR: 2512 stations matched to car links (passenger-car headline set, ramps excluded).")
H.append(f"  figA/B/C (facility scatter/GEH/bias, TOTAL-AADT) plot {int(allm_n)} after dropping {2512-int(allm_n)} "
         f"(~{(2512-int(allm_n))/2512*100:.0f}%) gross station→link")
H.append("  mismatches (ratio>=2.5 / model=0 / ramp-on-mainline / over-tolerance snap). The route & tier panels")
H.append("  keep all 2512 (model=0 stations retained as honest under-predictions).")
H.append("")
H.append("Per-facility TIER (FHWA F_SYSTEM, passenger-car; corr²_simpos = corr² on model>0 stations, PRIMARY):")
H.append(f"  {'tier':24s} {'n':>4s} {'GEH<5':>6s} {'±band':>6s} {'medbias':>8s} {'sim/obs':>8s} {'r²(>0)':>7s} {'trueR²':>7s}")
for t in ["Interstate","Other Freeway-Expressway","Principal Arterial","Minor Arterial","Major Collector","Minor Collector-Local"]:
    if t in ftier.index:
        x=ftier.loc[t]
        H.append(f"  {t:24s} {int(x.n):>4d} {x.GEH_lt5_pct:>5.0f}% {x.within_facband_pct:>5.0f}% "
                 f"{x.median_bias_pct:>+7.0f}% {x.median_ratio:>8.2f} {x.corr2_simpos:>7.2f} {x.R2_true:>7.2f}")
H.append("")
H.append("Read: PRINCIPAL/MINOR ARTERIALS VALIDATE (bias near 0, sim/obs ~0.75-1.00). Interstates are a")
H.append("DIAGNOSTIC, not a pass: the residual is CONSISTENT WITH through / non-resident PASSENGER traffic outside")
H.append("the resident-only scope (bias -44%) — a HYPOTHESIS, not independently confirmed here (freight/bus are")
H.append("already netted out of the observed target, so commercial traffic cannot explain the passenger-car residual;")
H.append("no truck/through overlay proves the mechanism). Fine collectors/local under-assign (sparse 10%-sample).")
H.append("")
H.append(f"Radial screenline (14 RADIAL-route crossings — I-95/I-83/I-70/US-40/MD-295, NOT a beltway cordon):")
H.append(f"  Ssim vs Sobs = {scr_pct:+.1f}%; one near-total miss (B0988 I-95 NE) drags the sum (see screenline_hybrid.csv).")
head = "\n".join(H)
(OUTDIR/"HEADLINE.txt").write_text(head+"\n")
print("\n"+head)
print("\nwrote", OUTDIR/"HEADLINE.txt")
