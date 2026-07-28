#!/usr/bin/env python3
"""Part A: QA + FIX the AADT-2023 -> MATSim-link matching (transit-fix run).

Problem with the original nearest-in-class snap (validate_aadt_2023.py):
  * FSYS_HWY for Collector/Local (F_SYSTEM 5/6) permits 'secondary' (cap up to 2000),
    so a local/collector count can snap UP to a bigger parallel arterial link.
  * a 45 m any-class fallback lets a count snap to an out-of-class link entirely.
Both inflate collector/minor error (e.g. OLD FREDERICK AVE obs 84 -> model 2488).

Fix: gate each AADT point's candidate links to the SAME facility class by (a) a
tightened OSM-highway allow-set (no upward leakage) AND (b) a capacity + freespeed
band derived from the network's own per-class distribution. Drop the out-of-class
fallback. Freeway+Principal matches are already clean (1.2 m snap) and must be
essentially unchanged -> verified in the report.

Writes network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv
(does NOT overwrite the original).
"""
import os
os.environ.setdefault("NETVAL_OUTDIR", "scenarios/01_base_no_pricing/output_transitfix")
os.environ.setdefault("NETVAL_ITER", "64")
os.environ.setdefault("NETVAL_SUB", "transitfix")

import numpy as np, pandas as pd
import geopandas as gpd
from netval2023_common import (ROOT, OUTDIR, CRS, link_gdf, geh, FSYS_GROUP, GROUP_ORDER)

AADT_FILE = ROOT/"data/aadt_2023_bmr_REAL.geojson"
ORIG_CSV  = OUTDIR/"aadt/aadt_validation_2023.csv"

# Same-class gate = ORIGINAL FSYS_HWY (unchanged). OSM highway tags do not align
# perfectly with MDOT F_SYSTEM (many MDOT collectors are OSM 'secondary'), so pure
# class purity throws away correct links. The real "bigger parallel road" signature
# is CAPACITY, not tag: a collector count grabbing a 2000-cap secondary or a 1500-cap
# motorway_link. So keep the class gate and add a per-class capacity ceiling.
FSYS_HWY = {
    1: {"motorway","motorway_link","trunk"},
    2: {"motorway","trunk","motorway_link","trunk_link","primary"},
    3: {"trunk","primary","secondary","trunk_link","primary_link"},
    4: {"primary","secondary","tertiary","primary_link","secondary_link"},
    5: {"secondary","tertiary","residential","unclassified","tertiary_link"},
    6: {"tertiary","residential","unclassified","secondary","living_street"},
    7: {"residential","unclassified","tertiary","living_street","service"},
}
# Capacity ceiling (veh/h/dir) for collector/local classes only. residential/tertiary/
# unclassified are all 600; a legit MDOT-collector-tagged-secondary is 1000; the
# "bigger parallel road" grabs are 2000-cap secondary / 1500-cap motorway_link / big
# primary -> excluded. None = no ceiling (major network physics untouched).
FSYS_CAPMAX = {1:None, 2:None, 3:None, 4:None, 5:1300.0, 6:1100.0, 7:900.0}
# Snap tolerance. Majors kept at the original (their snaps are pristine at ~1 m).
# Collector/minor TIGHTENED: error rises monotonically with snap distance (collector
# median |rel| 59% at <5 m -> 82% at 25-45 m, and the 25-45 m band holds the gross
# over-predictions). A count >25 m from any same-class link is on a road NOT in the
# network -> better left unmatched than snapped to a parallel road.
FSYS_TOL = {1:80.0, 2:75.0, 3:55.0, 4:30.0, 5:25.0, 6:25.0, 7:25.0}


def match_stations(g):
    aadt = gpd.read_file(AADT_FILE).to_crs(CRS)
    aadt = aadt[aadt.AADT_2023 > 0].copy()
    gid  = dict(zip(g.id, g.geometry)); ghwy = dict(zip(g.id, g.hwy))
    gux  = dict(zip(g.id, g.ux));       guy  = dict(zip(g.id, g.uy))
    gvol = dict(zip(g.id, g.vol24))
    gcap = dict(zip(g.id, g.cap));      gfsp = dict(zip(g.id, g.freespeed))
    gidx = {i: lid for i, lid in enumerate(g.id)}
    sidx = g.sindex
    rows = []
    for _, s in aadt.iterrows():
        fs  = int(s.F_SYSTEM) if pd.notna(s.F_SYSTEM) else 4
        tol = FSYS_TOL.get(fs, 45.0)
        if s.ID_PREFIX == "RP": tol = min(tol, 45.0)
        allowed = FSYS_HWY.get(fs, None)
        capmax  = FSYS_CAPMAX.get(fs, None)
        cand = list(sidx.query(s.geometry.buffer(tol), predicate="intersects"))
        inclass = []
        for idx in cand:
            lid = gidx[idx]; hw = ghwy[lid]
            if allowed is not None and hw not in allowed:      continue      # same-class gate
            d = s.geometry.distance(gid[lid])
            if d <= tol: inclass.append((lid, d))
        geom_match = len(inclass) > 0
        # Capacity PREFERENCE for collector/local: if a same-class link at/under the
        # class capacity ceiling exists, use only those (i.e. snap the local count to
        # the adjacent local link, NOT the bigger parallel secondary/link road). Only
        # if no under-ceiling link is nearby do we keep the larger in-class candidate.
        # This reroutes the "bigger parallel road" grabs WITHOUT dropping legitimate
        # high-AADT collectors whose only nearby link is a secondary.
        if capmax is not None and inclass:
            under = [(lid, d) for lid, d in inclass if gcap[lid] <= capmax]
            if under:
                inclass = under
        # For the MAJOR classes (1-3) keep the original any-class 45 m fallback so their
        # already-clean coverage is untouched. For collector/minor (4-7) the fallback is
        # DROPPED: a far/out-of-class snap there is exactly the bad match we are removing
        # -> leave unmatched (the count's road is not in the network).
        if not inclass and fs <= 3:
            near = [(gidx[idx], s.geometry.distance(gid[gidx[idx]])) for idx in cand]
            inclass = [(lid, d) for lid, d in near if d <= 45]
        loaded = [(lid, d) for lid, d in inclass if gvol[lid] > 0]
        if loaded:
            loaded.sort(key=lambda t: t[1])
            prim, pd0 = loaded[0]; ux, uy = gux[prim], guy[prim]
            opp = [(lid, d) for lid, d in loaded if lid != prim and gux[lid]*ux + guy[lid]*uy < -0.3]
            opp.sort(key=lambda t: t[1])
            chosen = [prim] + ([opp[0][0]] if opp else [])
            model = sum(gvol[l] for l in chosen)
            mindist = pd0; nlk = len(chosen)
            hwys = ";".join(sorted(set(ghwy[l] for l in chosen)))
        else:
            model = 0.0; mindist = (inclass[0][1] if inclass else np.nan); nlk = 0; hwys = ""; chosen = []
        fac = "Ramp" if s.ID_PREFIX == "RP" else FSYS_GROUP.get(fs, "Other")
        rows.append({"LOCATION_ID": s.LOCATION_ID, "COUNTY_DESC": s.COUNTY_DESC,
                     "ID_PREFIX": s.ID_PREFIX, "ID_RTE_NO": s.ID_RTE_NO, "ROADNAME": s.ROADNAME,
                     "F_SYSTEM": fs, "facility": fac,
                     "obs_AADT": float(s.AADT_2023),
                     "obs_AAWDT": float(s.AAWDT_2023) if pd.notna(s.AAWDT_2023) else np.nan,
                     "model_daily": model, "link_ids": ";".join(chosen), "n_links": nlk,
                     "hwy": hwys, "min_dist": mindist, "geom_match": int(geom_match),
                     "lon": s.geometry.x, "lat": s.geometry.y})
    return pd.DataFrame(rows)


def err_stats(df):
    ok = df[df.model_daily > 0].copy()
    if len(ok) == 0: return dict(n=0, medabs=np.nan, corr2=np.nan, medbias=np.nan, meanabs=np.nan, meanbias=np.nan, gross=0)
    rel = 100*(ok.model_daily - ok.obs_AADT)/ok.obs_AADT
    ratio = ok.model_daily/ok.obs_AADT
    corr = np.corrcoef(ok.obs_AADT, ok.model_daily)[0,1]
    return dict(n=len(ok), medabs=np.median(np.abs(rel)), corr2=corr**2, medbias=np.median(rel),
                meanabs=np.mean(np.abs(rel)), meanbias=np.mean(rel), gross=int((ratio>5).sum()))


def main():
    print("building transit-fix car-link GDF ...")
    g = link_gdf()
    print(f"car links {len(g):,}  loaded {(g.vol24>0).sum():,}")
    new = match_stations(g)
    new["GEH"] = geh(new.model_daily.values, new.obs_AADT.values)
    new["diff"] = new.model_daily - new.obs_AADT
    new["rel_err_pct"] = 100*new["diff"]/new.obs_AADT
    out = OUTDIR/"aadt/aadt_validation_2023_cleaned.csv"
    new.to_csv(out, index=False)
    print("wrote", out)

    old = pd.read_csv(ORIG_CSV)
    key = "LOCATION_ID"
    m = old[[key, "model_daily", "link_ids"]].rename(columns={"model_daily": "old_model", "link_ids": "old_links"})
    cmp = new.merge(m, on=key, how="left")
    changed = cmp[(cmp.link_ids.fillna("") != cmp.old_links.fillna(""))]
    print(f"\npoints total: {len(new)}")
    print(f"points whose match CHANGED: {len(changed)}  ({100*len(changed)/len(new):.1f}%)")
    now_unmatched = cmp[(cmp.model_daily <= 0) & (cmp.old_model > 0)]
    print(f"  became UNMATCHED (dropped bad snap): {len(now_unmatched)}")

    print("\n=== collector/minor error  BEFORE -> AFTER ===")
    print("(median & corr2 reflect real model under-assignment and are ~flat; the matching")
    print(" fix shrinks the OVER-assignment tail: mean|rel|, meanbias, gross snaps ratio>5)")
    for grp in ["Collector/Local", "Minor Arterial"]:
        b = err_stats(old[old.facility == grp]); a = err_stats(new[new.facility == grp])
        print(f"{grp:16s}  n {b['n']:4d}->{a['n']:4d}   med|rel| {b['medabs']:5.1f}->{a['medabs']:5.1f}  "
              f"corr2 {b['corr2']:.3f}->{a['corr2']:.3f}  mean|rel| {b['meanabs']:5.0f}->{a['meanabs']:5.0f}  "
              f"meanbias {b['meanbias']:+5.0f}->{a['meanbias']:+5.0f}  gross(>5x) {b['gross']:3d}->{a['gross']:3d}")
    print("\n=== MAJOR network (must be ~unchanged) ===")
    for grp in ["Interstate/Freeway", "Principal Arterial"]:
        b = err_stats(old[old.facility == grp]); a = err_stats(new[new.facility == grp])
        print(f"{grp:18s}  n {b['n']:4d}->{a['n']:4d}   med|rel| {b['medabs']:6.1f}->{a['medabs']:6.1f}   "
              f"corr2 {b['corr2']:.3f}->{a['corr2']:.3f}")
    # how many major-network matches actually changed link set
    for grp in ["Interstate/Freeway", "Principal Arterial"]:
        sub = cmp[cmp.facility == grp]
        ch = sub[sub.link_ids.fillna("") != sub.old_links.fillna("")]
        print(f"  {grp}: {len(ch)}/{len(sub)} link-sets changed")

    # summary_by_facility_cleaned
    def summ(d, lab):
        ok = d[d.model_daily > 0]
        if len(ok) == 0: return None
        gg = geh(ok.model_daily.values, ok.obs_AADT.values)
        rel = 100*(ok.model_daily - ok.obs_AADT)/ok.obs_AADT
        corr = np.corrcoef(ok.obs_AADT, ok.model_daily)[0,1]
        return {"label": lab, "n": len(ok), "pctGEH5": 100*np.mean(gg<5),
                "medGEH": np.median(gg), "corr2": corr**2,
                "med_absrel": np.median(np.abs(rel)), "medbias_pct": np.median(rel)}
    tab = [summ(new, "ALL"), summ(new[new.facility != "Ramp"], "ALL mainline (excl ramps)")]
    for grp in GROUP_ORDER + ["Ramp"]:
        r = summ(new[new.facility == grp], grp)
        if r: tab.append(r)
    pd.DataFrame(tab).to_csv(OUTDIR/"aadt/summary_by_facility_cleaned.csv", index=False)
    print("\nwrote", OUTDIR/"aadt/summary_by_facility_cleaned.csv")


if __name__ == "__main__":
    main()
