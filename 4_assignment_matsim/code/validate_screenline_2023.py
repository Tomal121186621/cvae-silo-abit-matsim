#!/usr/bin/env python3
"""Baltimore screenline validation (NYC-paper Fig. 16 analogue: East-River screenline, +1.8%).

Defines an I-695 Beltway EXTERNAL CORDON on the named principal facilities
(I-95 N & S, I-83, I-70, US-40 E & W, MD-295) -- one both-direction mainline
AADT-2023 station where each radial crosses the Beltway -- and sums MATSim(x10)
vs observed AADT_2023 across the screenline. Reports the total daily % difference
and the by-6-period distribution (NYC Fig.16 style). A wider "full external cordon"
(all principal radials crossing the Beltway) is reported alongside for robustness.

I-695 itself is the cordon LINE; its mainline is validated separately in the AADT
beltway breakdown (44 stations). Model side = both-carriageway link volume x10 from
64.linkstats. Observed by-period = AADT distributed with facility-average TMAS-2023
observed hourly fractions (documented approximation; AADT is a daily total).
"""
import numpy as np, pandas as pd
from netval2023_common import ROOT, OUTDIR, load_linkstats

AADT_VAL = OUTDIR/"aadt/aadt_validation_2023.csv"
PROFILES = OUTDIR/"tmas/station_profiles.csv"

# ---- screenline definitions: one both-direction mainline station per radial crossing the Beltway
# (LOCATION_ID -> (facility label, radial name, direction)).  See VALIDATION_2023 for the map.
NAMED = {   # exactly the task-named facilities: I-95 (N&S), I-83, I-70, US-40 (E&W), MD-295
    "B2532":  ("Interstate/Freeway", "I-95",   "SW (to Washington)"),
    "B0988":  ("Interstate/Freeway", "I-95",   "NE (JFK, to Delaware)"),
    "P0052":  ("Interstate/Freeway", "I-83",   "N (Harrisburg Expwy)"),
    "P0053":  ("Interstate/Freeway", "I-70",   "W (Beltway terminus)"),
    "B0945":  ("Principal Arterial", "US-40",  "W (National Pike)"),
    "B1202":  ("Principal Arterial", "US-40",  "E (Pulaski Hwy)"),
    "B0717":  ("Interstate/Freeway", "MD-295", "S (Balt-Wash Pkwy)"),
}
# wider external cordon: all principal radials crossing the Beltway (robustness context)
EXTRA = {
    "B030066":("Interstate/Freeway", "I-795",  "NW (Northwest Expwy)"),
    "B0628":  ("Interstate/Freeway", "I-97",   "S (to Annapolis)"),
    "B1024":  ("Principal Arterial", "MD-140", "NW (Reisterstown Rd)"),
    "B0939":  ("Principal Arterial", "MD-26",  "W (Liberty Rd)"),
    "B0617":  ("Principal Arterial", "MD-2",   "S (Ritchie Hwy)"),
    "B030058":("Interstate/Freeway", "MD-43",  "NE (White Marsh Blvd)"),
    "B1033":  ("Minor Arterial",     "MD-144", "W (Frederick Rd)"),
}

PERIODS = [("6-9AM",[6,7,8]), ("9AM-12PM",[9,10,11]), ("12-3PM",[12,13,14]),
           ("3-6PM",[15,16,17]), ("6-9PM",[18,19,20]), ("9PM-6AM",[21,22,23,0,1,2,3,4,5])]

def obs_period_fractions():
    """Facility-average observed hourly fractions from TMAS-2023 profiles -> 6-period shares."""
    p = pd.read_csv(PROFILES)
    fw = {1,2}   # F_SYSTEM freeway
    out = {}
    for label, grp in [("freeway", p[p.fs.isin(fw)]), ("arterial", p[~p.fs.isin(fw)])]:
        hrs = np.array([grp[f"obs_h{h}"].sum() for h in range(24)], float)
        hrs = hrs/hrs.sum()
        out[label] = {name: float(hrs[np.array(hh)].sum()) for name, hh in PERIODS}
    return out

def main():
    df = pd.read_csv(AADT_VAL, dtype={"LOCATION_ID":str}).set_index("LOCATION_ID")
    ls = load_linkstats()   # hourly h0..h23 x10, indexed by str LINK

    def build(defs, name):
        rows=[]
        for sid,(fac,rte,drc) in defs.items():
            if sid not in df.index:
                print(f"  !! {sid} not in AADT validation table"); continue
            r=df.loc[sid]
            lids=[x for x in str(r.link_ids).split(";") if x]
            hr=np.zeros(24)
            for lid in lids:
                if lid in ls.index:
                    hr += np.array([ls.loc[lid][f"h{h}"] for h in range(24)],float)
            rows.append({"station":sid,"facility":fac,"route":rte,"dir":drc,
                         "obs_AADT":float(r.obs_AADT),"model_daily":float(r.model_daily),
                         **{f"mh{h}":hr[h] for h in range(24)}})
        s=pd.DataFrame(rows)
        s.to_csv(OUTDIR/f"screenline_stations_{name}.csv", index=False)
        return s

    print("=== SCREENLINE STATIONS ===")
    named = build(NAMED, "named")
    full  = build({**NAMED, **EXTRA}, "full_cordon")

    ofrac = obs_period_fractions()
    def report(s, tag):
        obs=s.obs_AADT.sum(); mod=s.model_daily.sum()
        pct=100*(mod-obs)/obs
        print(f"\n--- {tag}: {len(s)} crossings ---")
        print(f"  observed AADT total : {obs:12,.0f}")
        print(f"  MATSim(x10) total   : {mod:12,.0f}")
        print(f"  TOTAL DAILY % DIFF  : {pct:+7.1f}%")
        # by period
        recs=[]
        for label,hh in PERIODS:
            msum=float(sum(s[f"mh{h}"].sum() for h in hh))
            # observed: split each station's AADT by its facility profile
            osum=0.0
            for _,rr in s.iterrows():
                fk="freeway" if rr.facility=="Interstate/Freeway" else "arterial"
                osum += rr.obs_AADT*ofrac[fk][label]
            recs.append({"period":label,"obs":osum,"model":msum,"diff_pct":100*(msum-osum)/osum if osum>0 else np.nan})
        pt=pd.DataFrame(recs)
        print(pt.to_string(index=False,formatters={"obs":lambda v:f"{v:,.0f}","model":lambda v:f"{v:,.0f}","diff_pct":lambda v:f"{v:+.1f}%"}))
        pt.insert(0,"screenline",tag)
        avgabs=pt.diff_pct.abs().mean()
        print(f"  by-period avg |%diff|: {avgabs:.1f}%  (max {pt.diff_pct.abs().max():.1f}%)")
        return {"screenline":tag,"n":len(s),"obs_total":obs,"model_total":mod,
                "total_diff_pct":pct,"byperiod_avgabs_pct":avgabs}, pt

    sum_named, per_named = report(named, "Named-facility screenline (I-95 N&S, I-83, I-70, US-40 E&W, MD-295)")
    sum_full,  per_full  = report(full,  "Full external cordon (all principal radials at Beltway)")

    pd.DataFrame([sum_named,sum_full]).to_csv(OUTDIR/"screenline_summary.csv", index=False)
    pd.concat([per_named,per_full]).to_csv(OUTDIR/"screenline_by_period.csv", index=False)
    print(f"\nwrote {OUTDIR/'screenline_summary.csv'}")
    print(f"wrote {OUTDIR/'screenline_by_period.csv'}")
    print(f"wrote screenline_stations_named.csv / screenline_stations_full_cordon.csv")

if __name__=="__main__":
    main()
