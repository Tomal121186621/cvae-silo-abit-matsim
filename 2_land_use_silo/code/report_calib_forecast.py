#!/usr/bin/env python3
"""Calibrate -> Forecast -> Validate report.

Splits a per-year validation summary into the CALIBRATION window (2016-2020, model fed actual
ACS targets) and the FORECAST window (2021-2023, model fed only extrapolated targets - blind to
actual ACS). The forecast-window error vs ACTUAL ACS is the true out-of-sample performance.
Optionally compares against the free-run (no-targeting) baseline summary.

Usage: python report_calib_forecast.py <framework_summary.csv> [baseline_summary.csv]
"""
import sys, pandas as pd, numpy as np
tv=["hhSize","autos","dwellingType","hh_inc9","age_bin","gender","race4","occ_silo"]
CALIB=[2016,2017,2018,2019,2020]; FORE=[2021,2022,2023]
STATES=["MD","VA","PA","DE","WV","DC"]

def meanTV(df,st,yrs):
    d=df[(df.state==st)&(df.variable.isin(tv))&(df.year.isin(yrs))]
    return d.groupby("year").tv.mean().mean() if len(d) else float("nan")

fw=pd.read_csv(sys.argv[1])
base=pd.read_csv(sys.argv[2]) if len(sys.argv)>2 else None
print("="*72)
print("CALIBRATE (2016-2020, in-sample) -> FORECAST (2021-2023, OUT-OF-SAMPLE)")
print("mean TV across 8 variables; FORECAST column = true forecast skill vs ACS")
print("="*72)
hdr=f"{'state':>6} {'calib(in-samp)':>15} {'FORECAST(oos)':>14}"
if base is not None: hdr+=f" {'baseline-fore':>14} {'improvement':>12}"
print(hdr)
for st in STATES:
    c=meanTV(fw,st,CALIB); f=meanTV(fw,st,FORE)
    line=f"{st:>6} {c:>15.3f} {f:>14.3f}"
    if base is not None:
        bf=meanTV(base,st,FORE); imp=bf-f
        line+=f" {bf:>14.3f} {imp:>+12.3f}"
    print(line)
# per-variable forecast skill (DC + region)
print("\nForecast-window (2021-2023) mean TV per variable:")
print(f"{'variable':>12} "+" ".join(f"{s:>7}" for s in STATES))
for v in tv:
    row=f"{v:>12} "
    for st in STATES:
        d=fw[(fw.state==st)&(fw.variable==v)&(fw.year.isin(FORE))]
        row+=f"{d.tv.mean():>7.3f} " if len(d) else f"{'-':>7} "
    print(row)
print("\n(in-sample should be low by construction; FORECAST is the headline performance.)")
