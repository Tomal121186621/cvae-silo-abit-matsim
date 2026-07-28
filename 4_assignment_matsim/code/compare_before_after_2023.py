#!/usr/bin/env python3
"""Before -> after network-validation comparison: resident-only base vs cordon-calibrated run.

Reads the two AADT per-station validation CSVs (base + calibrated) and the two TMAS CSVs, and prints
the headline before/after table: freeway-mainline bias, overall bias, %GEH<5 (overall + freeway), R2,
AM/PM peak magnitude, and I-695 (should stay good).
"""
import numpy as np, pandas as pd
from pathlib import Path
from netval2023_common import ROOT, geh

BASE = ROOT/"network_validation_2023/aadt/aadt_validation_2023.csv"
CAL  = ROOT/"network_validation_2023/calibrated/aadt/aadt_validation_2023.csv"
BASE_T = ROOT/"network_validation_2023/tmas/tmas_validation_2023.csv"
CAL_T  = ROOT/"network_validation_2023/calibrated/tmas/tmas_validation_2023.csv"

def seg(df, mask):
    d=df[mask & (df.model_daily>0)].copy()
    if len(d)==0: return dict(n=0)
    m=d.model_daily.values; o=d.obs_AADT.values; g=geh(m,o)
    ss_res=np.sum((m-o)**2); ss_tot=np.sum((o-o.mean())**2)
    return dict(n=len(d), pctGEH5=100*np.mean(g<5), pctGEH10=100*np.mean(g<10),
                medGEH=np.median(g), medbias=100*np.median((m-o)/o),
                aggratio=m.sum()/o.sum(), R2=1-ss_res/ss_tot if ss_tot>0 else np.nan,
                corr2=np.corrcoef(o,m)[0,1]**2)

def fw_mainline(df): return (df.ID_PREFIX.isin(["IS","US"])) & (df.facility=="Interstate/Freeway")
def i695(df): return df.ROADNAME.astype(str).str.contains("BELTWAY", case=False, na=False)

def row(label, b, c, key, fmt="{:+.0f}%", pct=True):
    bv=b.get(key,np.nan); cv=c.get(key,np.nan)
    return f"{label:32} {fmt.format(bv):>12} {fmt.format(cv):>12}"

def main():
    b=pd.read_csv(BASE); c=pd.read_csv(CAL)
    segs=[("Overall (all stations)", np.ones(len(b),bool), np.ones(len(c),bool)),
          ("Freeway mainline IS/US", fw_mainline(b), fw_mainline(c)),
          ("I-695 Beltway",          i695(b),        i695(c))]
    print(f"\n{'='*70}\nAADT 2023 daily validation — BEFORE (resident-only) -> AFTER (calibrated)\n{'='*70}")
    print(f"{'segment':32} {'metric':>10}   {'BEFORE':>10}  {'AFTER':>10}")
    for name,mb,mc in segs:
        B=seg(b,mb); C=seg(c,mc)
        if B.get('n',0)==0: continue
        print(f"\n{name}  (n={B['n']} -> {C['n']})")
        print(f"  {'agg model/obs ratio':30} {B['aggratio']:>10.2f}  {C['aggratio']:>10.2f}")
        print(f"  {'median bias':30} {B['medbias']:>9.0f}% {C['medbias']:>9.0f}%")
        print(f"  {'% GEH<5':30} {B['pctGEH5']:>9.1f}% {C['pctGEH5']:>9.1f}%")
        print(f"  {'% GEH<10':30} {B['pctGEH10']:>9.1f}% {C['pctGEH10']:>9.1f}%")
        print(f"  {'median GEH':30} {B['medGEH']:>10.0f}  {C['medGEH']:>10.0f}")
        print(f"  {'R2':30} {B['R2']:>10.2f}  {C['R2']:>10.2f}")
        print(f"  {'corr2':30} {B['corr2']:>10.2f}  {C['corr2']:>10.2f}")

    # TMAS peaks
    try:
        tb=pd.read_csv(BASE_T); tc=pd.read_csv(CAL_T)
        def peak(t, fwonly=False):
            d=t[t.fs.isin([1,2])] if fwonly else t
            return dict(n=len(d),
                        am_bias=100*np.median((d.model_am-d.obs_am)/d.obs_am),
                        pm_bias=100*np.median((d.model_pm-d.obs_pm)/d.obs_pm),
                        corr=d.profile_corr.mean())
        print(f"\n{'='*70}\nTMAS 2023 hourly (weekday) — BEFORE -> AFTER\n{'='*70}")
        for lbl,fw in [("All TMAS",False),("Freeway TMAS",True)]:
            B=peak(tb,fw); C=peak(tc,fw)
            print(f"\n{lbl} (n={B['n']})")
            print(f"  {'AM-peak median bias':30} {B['am_bias']:>9.0f}% {C['am_bias']:>9.0f}%")
            print(f"  {'PM-peak median bias':30} {B['pm_bias']:>9.0f}% {C['pm_bias']:>9.0f}%")
            print(f"  {'mean profile corr':30} {B['corr']:>10.2f}  {C['corr']:>10.2f}")
    except FileNotFoundError as e:
        print("\n(TMAS comparison skipped:", e, ")")

if __name__=="__main__":
    main()
