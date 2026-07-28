#!/usr/bin/env python3
"""LODES-calibrated workplace RE-ASSIGNMENT (full model fix, task #66).

Replaces (a) SILO's over-dispersed workplace assignment (BMR-resident commutes 45km vs RTS 16km; 49% of BMR
jobs to outsiders vs LODES 24%) and (b) the ABIT's home-gravity re-draw (sampleWorkZone, which discards SILO
workplaces and loses out-of-state->BMR commutes). Method: take the OBSERVED LODES home-county->work-county
commute flows, disaggregate to zone->zone by (home-zone worker share) x (work-zone job share) x exp(-beta*t),
then draw each SILO worker a work zone from their home-zone row. Reproduces the real 24% inflow / 7.6%
out-of-state with realistic commute lengths, BY CONSTRUCTION (inherits LODES structure).

Output: worker_workplace_zone.csv  (person_id, home_zone, work_zone)  -> consumed by the patched ABIT reader.
"""
import gzip, collections, numpy as np, pandas as pd
from pathlib import Path

SILO = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/scenOutput/updated_vae_calib5/microData")
ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
LODES_OD = Path("/private/tmp/claude-501/-Users-tomal-Documents-SILO-MITO-Chayan-VAE-SILO-MITO-MATSIM/cc2fa892-5cdc-4bdb-aad9-d20437e1ee41/scratchpad/lodes_county_od.csv")
ZS = ROOT / "inputs/zoneSystem.csv"
ZC = ROOT.parent / "VAE-SILO-MITO-MATSIM/Tour Based MITO/data/zone_coords.csv"
BETA = 0.06   # min^-1 within-county friction; light (county already fixes the coarse structure)
SEED = 20230

def main():
    rng = np.random.default_rng(SEED)
    zs = pd.read_csv(ZS); z2c = dict(zip(zs["ZoneId"], zs["COUNTYFIPS"]))
    zc = pd.read_csv(ZC).set_index("zone")
    # --- workers by home zone (SILO employed), jobs by work zone (SILO jj) ---
    dd = pd.read_csv(SILO/"dd_2023.csv", usecols=["hhID","zone"]); hz = dict(zip(dd.hhID, dd.zone))
    pp = pd.read_csv(SILO/"pp_2023.csv", usecols=["id","hhid","occupation"])
    pp = pp[pp.occupation == 1].copy(); pp["homez"] = pp["hhid"].map(hz)
    pp = pp.dropna(subset=["homez"]); pp["homez"] = pp["homez"].astype(int); pp["hc"] = pp["homez"].map(z2c)
    jj = pd.read_csv(SILO/"jj_2023.csv", usecols=["zone"])
    jobs_z = jj.groupby("zone").size(); jobs_z = jobs_z[jobs_z.index.isin(zc.index)]
    jobz_df = pd.DataFrame({"zone": jobs_z.index, "jobs": jobs_z.values})
    jobz_df["wc"] = jobz_df["zone"].map(z2c)
    workers_z = pp.groupby("homez").size()
    # --- LODES county OD -> target commute proportions ---
    lod = pd.read_csv(LODES_OD)
    # keep only counties present in our zone system
    counties = set(z2c.values())
    lod = lod[lod.home_county.isin(counties) & lod.work_county.isin(counties)]
    print(f"workers(SILO employed)={len(pp):,}  jobs(SILO)={int(jobs_z.sum()):,}  LODES OD cells={len(lod):,}")

    # zone centroids for friction
    cx = zc["coordX"].to_dict(); cy = zc["coordY"].to_dict()
    def tmin(z1, z2):  # crude free-flow min: straight-line km /50kmh *60, x1.3
        d = np.hypot(cx[z1]-cx[z2], cy[z1]-cy[z2])/1000*1.3
        return d/50*60

    # --- LODES-FLOW-DRIVEN assign (absolute counts): the LODES matrix only covers MD-work jobs, so it IS the
    #     set of commutes-into-MD. For each (home county h -> MD work county w) cell, take LODES(h,w) workers
    #     (scaled to the SILO worker pool) from home county h and assign them a job in w (zone ~ job density).
    #     SILO workers in h NOT drawn into an MD job work LOCALLY (out-of-scope: home-state job, work_zone=-1;
    #     the BMR cut drops them). This reproduces LODES's 24% inflow / 7.6% out-of-state BY CONSTRUCTION. ---
    # per work county: zone ids, job counts, and centroid arrays (for distance friction)
    wc_zone = {}
    for wc, g in jobz_df.groupby("wc"):
        zzs = g["zone"].to_numpy()
        wc_zone[int(wc)] = (zzs, g["jobs"].to_numpy(float),
                            np.array([cx[z] for z in zzs]), np.array([cy[z] for z in zzs]))
    hxall = pp["homez"].map(cx).to_numpy(); hyall = pp["homez"].map(cy).to_numpy()
    pp = pp.reset_index(drop=True)
    work_zone = np.full(len(pp), -1, dtype=np.int64)
    idx_by_hc = {int(hc): np.asarray(idx) for hc, idx in pp.groupby("hc").groups.items()}
    BETA_KM = float(__import__("os").environ.get("WP_BETA", "0.18"))   # per-km within-work-county friction
    for hc, g in lod.groupby("home_county"):
        pool = idx_by_hc.get(int(hc))
        if pool is None or len(pool) == 0: continue
        avail = pool.copy(); rng.shuffle(avail); ptr = 0
        cells = g.sort_values("workers", ascending=False)
        demand = cells["workers"].to_numpy(float); scale = min(1.0, len(avail)/max(1.0, demand.sum()))
        for wc, dem in zip(cells["work_county"].to_numpy(), demand):
            take = int(round(dem*scale))
            if take <= 0 or ptr >= len(avail): continue
            take = min(take, len(avail)-ptr); sel = avail[ptr:ptr+take]; ptr += take
            zz = wc_zone.get(int(wc))
            if zz is None:
                work_zone[sel] = pp["homez"].to_numpy()[sel]; continue
            zzs, jb, zx, zy = zz
            # distance-friction job draw per worker (workers in this cell share the same home county but
            # different home zones -> use each worker's own home coord). Vectorized over the cell's workers.
            hx = hxall[sel][:, None]; hy = hyall[sel][:, None]
            dkm = np.hypot(hx - zx[None, :], hy - zy[None, :]) / 1000.0
            w = jb[None, :] * np.exp(-BETA_KM * dkm)                # (take, nzones)
            w /= w.sum(axis=1, keepdims=True)
            cumw = np.cumsum(w, axis=1); u = rng.random(take)[:, None]
            pick = (cumw < u).sum(axis=1).clip(0, len(zzs)-1)
            work_zone[sel] = zzs[pick]
    res = pd.DataFrame({"person_id": pp["id"].to_numpy(), "home_zone": pp["homez"].to_numpy(), "work_zone": work_zone})
    outp = ROOT/"ABIT/input/maryland/worker_workplace_zone.csv"
    res.to_csv(outp, index=False)
    # --- verify vs LODES ---
    BMRc = {24003,24005,24013,24025,24027,24510}
    res["hc"] = res["home_zone"].map(z2c); res["wc2"] = res["work_zone"].map(z2c)
    bmrjob = res[res["wc2"].isin(BMRc)]
    inflow = (~bmrjob["hc"].isin(BMRc)).mean()*100
    oos = (bmrjob["hc"]//1000 != 24).mean()*100
    km = np.hypot(res["home_zone"].map(cx)-res["work_zone"].map(cx), res["home_zone"].map(cy)-res["work_zone"].map(cy))/1000
    print(f"RE-ASSIGNED: BMR-job inflow={inflow:.0f}% (LODES 24%)  out-of-state={oos:.1f}% (LODES 7.6%)")
    print(f"  commute straight-line: mean={km.mean():.0f}km median={km.median():.0f}km (SILO was 47/34; RTS ~16)")
    print(f"  saved {outp} ({len(res):,} workers)")

if __name__ == "__main__":
    main()
