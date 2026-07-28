#!/usr/bin/env python3
"""Component 3/4 -- validate a MATSim run against a given station set (CALIBRATION or HELD-OUT).

Usage:  validate_resident_targets.py <run_dir> <station_csv> [out.json]

Reads the run's *latest* linkstats (auto-detected: highest ITERS/it.N/N.linkstats.txt.gz),
scales it to regional volumes (x1/flowCap; NETVAL_FLOWCAP env, default 0.10 -> x10),
joins the station set to link_ids (from aadt_validation_2023_cleaned.csv), recomputes
model_daily, and writes a gate json with per-facility + overall corr2 / GEH / bias and the
per-facility median(sim/obs) ratio the capacity SPSA step consumes.

Reuses metrics() / geh() / sim_daily_lookup() logic from validate_base_hybrid; kept local
so importing this file never triggers that module's side effects.
"""
import glob, gzip, json, os, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AADT = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
# Beltway cordon screenline stations (validation-only; from validate_base_hybrid NAMED+EXTRA)
SCREEN = {"B2532","B0988","P0052","P0053","B0945","B1202","B0717",
          "B030066","B0628","B1024","B0939","B0617","B030058","B1033"}
GROUP_ORDER = ["Principal Arterial", "Minor Arterial", "Collector/Local", "Interstate/Freeway"]


def geh(model, obs):
    model = np.asarray(model, float); obs = np.asarray(obs, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.sqrt(2*(model-obs)**2/(model+obs))
    return np.where((model+obs) > 0, g, np.nan)


def metrics(obs, sim):
    obs = np.asarray(obs, float); sim = np.asarray(sim, float)
    ok = (sim > 0) & np.isfinite(obs) & (obs > 0); obs = obs[ok]; sim = sim[ok]
    if len(obs) < 3:
        return dict(n=int(len(obs)), corr2=np.nan, medGEH=np.nan, pctGEH5=np.nan,
                    meanbias=np.nan, medbias=np.nan, median_ratio=np.nan)
    g = geh(sim, obs); rel = (sim-obs)/obs*100; ratio = sim/obs
    r = np.corrcoef(obs, sim)[0, 1]
    return dict(n=int(len(obs)), corr2=float(r*r), medGEH=float(np.nanmedian(g)),
                pctGEH5=float(np.nanmean(g < 5)*100), meanbias=float(rel.mean()),
                medbias=float(np.median(rel)), median_ratio=float(np.median(ratio)))


def latest_linkstats(run_dir):
    cands = glob.glob(str(Path(run_dir)/"ITERS/it.*/*.linkstats.txt.gz"))
    if not cands:
        sys.exit(f"ERROR: no linkstats under {run_dir}/ITERS/it.*/")
    def it_of(p):
        m = re.search(r"it\.(\d+)", p)
        return int(m.group(1)) if m else -1
    return max(cands, key=it_of), max(map(it_of, cands))


def load_linkstats(path, scale):
    df = pd.read_csv(path, sep="\t", dtype={"LINK": str})
    df["vol24"] = df["HRS0-24avg"] * scale
    return df.set_index("LINK")["vol24"]


def sim_daily_lookup(ls):
    def f(link_ids):
        s = 0.0
        for lid in str(link_ids).split(";"):
            lid = lid.strip()
            if lid and lid in ls.index:
                s += float(ls.loc[lid])
        return s
    return f


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: validate_resident_targets.py <run_dir> <station_csv> [out.json]")
    run_dir = sys.argv[1]; station_csv = sys.argv[2]
    outjson = sys.argv[3] if len(sys.argv) > 3 else str(Path(run_dir)/"calibration_gate.json")
    flowcap = float(os.environ.get("NETVAL_FLOWCAP", "0.10"))
    scale = 1.0/flowcap

    ls_path, it = latest_linkstats(run_dir)
    ls = load_linkstats(ls_path, scale)

    # station set (calibration or holdout) -> join link_ids from the master AADT table
    st = pd.read_csv(station_csv)
    link_map = pd.read_csv(AADT)[["LOCATION_ID", "link_ids"]]
    d = st.merge(link_map, on="LOCATION_ID", how="left")
    f = sim_daily_lookup(ls)
    d["model_daily"] = d.link_ids.apply(f)
    d["ratio"] = d.model_daily / d.obs_AADT.replace(0, np.nan)

    per = {}
    for fac in GROUP_ORDER:
        sub = d[d.facility == fac]
        if len(sub):
            per[fac] = metrics(sub.obs_AADT, sub.model_daily)
    overall = metrics(d.obs_AADT, d.model_daily)  # all facilities in the set

    # validation-only screenline sum over any cordon stations present in this set
    sc = d[d.LOCATION_ID.isin(SCREEN)]
    scr_obs = float(sc.obs_AADT.sum()); scr_sim = float(sc.model_daily.sum())
    scr_pct = (scr_sim-scr_obs)/scr_obs*100 if scr_obs > 0 else None

    gate = dict(
        run_dir=str(run_dir), station_csv=str(station_csv), linkstats=str(ls_path),
        iteration=it, flowcap=flowcap, sample_scale=scale, n_stations=int(len(d)),
        overall=overall, per_facility=per,
        screenline=dict(n=int(len(sc)), obs=scr_obs, sim=scr_sim, pct=scr_pct),
    )
    Path(outjson).write_text(json.dumps(gate, indent=2))

    print(f"=== {Path(station_csv).name} vs {run_dir} (it.{it}, scale x{scale:.2f}) ===")
    print(f"OVERALL  n={overall['n']:4d}  corr2={overall['corr2']:.3f}  "
          f"medGEH={overall['medGEH']:.2f}  GEH<5={overall['pctGEH5']:.0f}%  "
          f"medbias={overall['medbias']:+.1f}%  medratio={overall['median_ratio']:.3f}")
    for fac, m in per.items():
        print(f"  {fac:<20} n={m['n']:4d}  corr2={m['corr2']:.3f}  medGEH={m['medGEH']:.2f}  "
              f"GEH<5={m['pctGEH5']:.0f}%  medbias={m['medbias']:+.1f}%  medratio={m['median_ratio']:.3f}")
    if scr_pct is not None:
        print(f"  screenline (n={len(sc)}): sim {scr_sim:,.0f} vs obs {scr_obs:,.0f} = {scr_pct:+.1f}%")
    print("wrote", outjson)


if __name__ == "__main__":
    main()
