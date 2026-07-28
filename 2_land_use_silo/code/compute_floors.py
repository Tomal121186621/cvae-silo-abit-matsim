#!/usr/bin/env python3
"""Identifiability (sampling-noise) FLOOR per state x variable.

The model is compared to the ACS 5-yr estimate, which itself has sampling error. Even a perfect
model cannot match ACS closer than the ACS estimate matches the true population. We estimate that
irreducible floor by nonparametric (survey) bootstrap of the ACS sample: resample rows with
replacement, recompute the weighted distribution, TV vs the full-sample estimate; the mean over
reps is the floor. An observed TV at or below the floor means "as good as the data allows."

Writes floors_<year>.csv (state, variable, floor_tv, n_eff). Default year 2023 (forecast horizon).
"""
import sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

HERE=Path(__file__).resolve().parent; USILO=HERE.parent; VAL=USILO/"validation"
spec=importlib.util.spec_from_file_location("va", HERE/"validate_allstates.py")
va=importlib.util.module_from_spec(spec); spec.loader.exec_module(va)   # gives load_acs6, STATES6
YEAR=int(sys.argv[1]) if len(sys.argv)>1 else 2023
B=60; rng=np.random.default_rng(0)
HHV=[("hhSize",range(1,8)),("autos",range(0,4)),("dwellingType",range(1,6)),("hh_inc9",range(0,9))]
PPV=[("age_bin",range(0,18)),("gender",[1,2]),("race4",["white","black","hispanic","other"]),("occ_silo",range(0,5))]

def wdist(vals,w,cats):
    idx={c:i for i,c in enumerate(cats)}; h=np.zeros(len(cats))
    v=vals.to_numpy(); w=np.asarray(w,float)
    for val,wt in zip(v,w):
        j=idx.get(val);
        if j is not None: h[j]+=wt
    s=h.sum(); return h/s if s>0 else h
def tv(p,q): return 0.5*np.abs(p-q).sum()
def neff(w): w=np.asarray(w,float); return (w.sum()**2)/np.maximum((w*w).sum(),1e-9)

rh,rp=va.load_acs6(YEAR)
rows=[]
for st in ["MD","VA","PA","DE","WV","DC"]:
    H=rh[rh.state==st]; P=rp[rp.state==st]
    if len(H)==0: continue
    for nm,cats in HHV:
        full=wdist(H[nm],H.w,list(cats)); n=len(H); wv=H.w.to_numpy()
        fl=np.mean([tv(wdist(H[nm].iloc[(b:=rng.integers(0,n,n))],wv[b],list(cats)),full) for _ in range(B)])
        rows.append({"state":st,"variable":nm,"floor_tv":round(float(fl),4),"n_eff":int(neff(H.w))})
    for nm,cats in PPV:
        full=wdist(P[nm],P.w,list(cats)); n=len(P); wv=P.w.to_numpy()
        fl=np.mean([tv(wdist(P[nm].iloc[(b:=rng.integers(0,n,n))],wv[b],list(cats)),full) for _ in range(B)])
        rows.append({"state":st,"variable":nm,"floor_tv":round(float(fl),4),"n_eff":int(neff(P.w))})
    print(f"{st}: floors done (hh n_eff~{int(neff(H.w)):,})")
df=pd.DataFrame(rows); df.to_csv(VAL/f"floors_{YEAR}.csv",index=False)
piv=df.pivot(index="variable",columns="state",values="floor_tv")
print(f"\n=== Identifiability floor (irreducible TV from ACS noise), {YEAR} ===")
print(piv.reindex([v for v,_ in HHV]+[v for v,_ in PPV]).to_string())
print(f"\nsaved floors_{YEAR}.csv  (observed TV <= floor => as accurate as ACS allows)")
