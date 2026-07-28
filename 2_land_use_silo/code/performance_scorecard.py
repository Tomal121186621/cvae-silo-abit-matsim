#!/usr/bin/env python3
"""SILO model-performance SCORECARD (the measurement framework).

Combines, for the FORECAST window (2021-2023, out-of-sample), per state x variable:
  - observed TV vs ACS (forecast skill),
  - identifiability floor (irreducible ACS noise, from compute_floors.py),
  - excess = max(0, TV - floor)  -> the real, addressable error,
  - forecast SKILL SCORE vs the free-run baseline: 1 - TV_model/TV_baseline (>0 = beats baseline),
  - verdict: EXCELLENT (TV<=1.5*floor), GOOD (TV<0.05), FAIR (<0.10), POOR (>=0.10).
Also reports CALIBRATION-window (2016-2020) mean TV (in-sample fit).

Usage: python performance_scorecard.py <model_summary.csv> [baseline_summary.csv]
  default model = ../validation/by_year_acs_fcast/summary.csv (framework) if present, else baseline.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

HERE=Path(__file__).resolve().parent; VAL=HERE.parent/"validation"
TV=["hhSize","autos","dwellingType","hh_inc9","age_bin","gender","race4","occ_silo"]
STATES=["MD","VA","PA","DE","WV","DC"]; CALIB=list(range(2016,2021)); FORE=[2021,2022,2023]
floors=pd.read_csv(VAL/"floors_2023.csv")
FL={(r.state,r.variable):r.floor_tv for r in floors.itertuples()}

mp=Path(sys.argv[1]) if len(sys.argv)>1 else (VAL/"by_year_acs_fcast"/"summary.csv" if (VAL/"by_year_acs_fcast"/"summary.csv").exists() else VAL/"_incomefix_FULL_summary.csv")
model=pd.read_csv(mp)
base=pd.read_csv(sys.argv[2]) if len(sys.argv)>2 else pd.read_csv(VAL/"_incomefix_FULL_summary.csv")
print(f"MODEL    = {mp}")

def fyTV(df,st,v):
    d=df[(df.state==st)&(df.variable==v)&(df.year.isin(FORE))]; return d.tv.mean() if len(d) else np.nan
def caTV(df,st,v):
    d=df[(df.state==st)&(df.variable==v)&(df.year.isin(CALIB))]; return d.tv.mean() if len(d) else np.nan

def verdict(tvv,fl):
    if np.isnan(tvv): return "n/a"
    if tvv<=1.5*fl: return "EXCELLENT"
    if tvv<0.05: return "GOOD"
    if tvv<0.10: return "FAIR"
    return "POOR"

rows=[]
for st in STATES:
    for v in TV:
        t=fyTV(model,st,v); c=caTV(model,st,v); fl=FL.get((st,v),np.nan); bt=fyTV(base,st,v)
        skill=(1-t/bt) if (bt and not np.isnan(bt) and bt>0 and not np.isnan(t)) else np.nan
        rows.append({"state":st,"variable":v,"calib_TV":round(c,4) if not np.isnan(c) else None,
                     "forecast_TV":round(t,4) if not np.isnan(t) else None,"floor":fl,
                     "excess":round(max(0,t-fl),4) if not np.isnan(t) else None,
                     "skill_vs_base":round(skill,3) if not np.isnan(skill) else None,
                     "verdict":verdict(t,fl)})
sc=pd.DataFrame(rows); sc.to_csv(VAL/"scorecard_detail.csv",index=False)

# per-state aggregate
agg=[]
for st in STATES:
    s=sc[sc.state==st]
    agg.append({"state":st,
                "calib_meanTV":round(np.nanmean([r for r in s.calib_TV if r is not None]),4),
                "forecast_meanTV":round(np.nanmean([r for r in s.forecast_TV if r is not None]),4),
                "mean_excess":round(np.nanmean([r for r in s.excess if r is not None]),4),
                "mean_skill_vs_base":round(np.nanmean([r for r in s.skill_vs_base if r is not None]),3),
                "vars_under_5pct":int(sum(1 for r in s.forecast_TV if r is not None and r<0.05)),
                "vars_at_floor":int(sum(1 for _,r in s.iterrows() if r.verdict=="EXCELLENT"))})
ag=pd.DataFrame(agg); ag.to_csv(VAL/"scorecard_by_state.csv",index=False)
print("\n================  PERFORMANCE SCORECARD (forecast window 2021-2023)  ================")
print(ag.to_string(index=False))
print("\nvars_under_5pct = of 8 variables, how many forecast within 5% | vars_at_floor = within 1.5x ACS noise")
print("mean_skill_vs_base>0 means the framework forecasts better than the free-run baseline")
print(f"\nsaved scorecard_by_state.csv, scorecard_detail.csv")
