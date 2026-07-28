#!/usr/bin/env python3
"""Out-of-sample validation of the SPSA-calibrated network (step 6).

Compares simulated link volumes to observed 2023 AADT on the HELD-OUT stations (never shown to SPSA) and,
side by side, the CALIBRATION stations (the over-fit check). If the held-out fit is close to the
calibration fit, the calibration generalised rather than memorised.

Reuses netval2023_common: point it at the calibrated full-population run's output, e.g.
    NETVAL_OUTDIR=scenarios/02_i695_congestion_pricing/output_base/base_v8_loaded \
    NETVAL_ITER=64 NETVAL_SUB=spsa_holdout \
    python code/validate_holdout.py

Uses the pre-matched link ids in spsa_{calibration,holdout}_stations.csv (no re-matching), sums each
station's matched-link 24h volumes (netval loads them x10 = full-scale for flowCap 0.10), and reports
corr2 / median GEH / %GEH<5 / %RMSE / mean rel-bias, overall and by facility, for each set.

Output: <NETVAL OUTDIR-derived>/network_validation_2023[/<SUB>]/summary.csv + a printed headline.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netval2023_common as nv

ROOT = nv.ROOT
CAL = ROOT / "network_validation_2023/calibration/spsa_calibration_stations.csv"
HLD = ROOT / "network_validation_2023/calibration/spsa_holdout_stations.csv"
GROUP_ORDER = nv.GROUP_ORDER


def station_sim(df, vols):
    out = df.copy()
    def sumv(s):
        ls = str(s).replace(";", ",").split(",")
        return sum(float(vols.get(l.strip(), vols.get(l.strip(), 0.0)) or 0.0)
                   for l in ls if l.strip() and l.strip() != "nan")
    out["sim"] = out["matched_link_ids"].apply(sumv)
    out["obs"] = pd.to_numeric(out["obs_AADT"], errors="coerce")
    return out[(out["obs"] > 0)]


def metrics(sub):
    if len(sub) < 2:
        return dict(n=len(sub), corr2=np.nan, medGEH=np.nan, pctGEH5=np.nan, rmse_pct=np.nan, bias_pct=np.nan)
    sim = sub["sim"].to_numpy(float); obs = sub["obs"].to_numpy(float)
    geh = nv.geh(sim, obs)
    rel = (sim - obs) / obs
    return dict(n=int(len(sub)),
                corr2=float(np.corrcoef(sim, obs)[0, 1] ** 2),
                medGEH=float(np.nanmedian(geh)),
                pctGEH5=float(100 * np.nanmean(geh < 5)),
                rmse_pct=float(100 * np.sqrt(np.mean(rel ** 2))),
                bias_pct=float(100 * np.mean(rel)))


def report(name, df, vols, rows):
    s = station_sim(df, vols)
    m = metrics(s); m.update(set=name, facility="ALL"); rows.append(m)
    print(f"\n=== {name} ({m['n']} stations) ===")
    print(f"  corr2={m['corr2']:.3f}  medGEH={m['medGEH']:.1f}  %GEH<5={m['pctGEH5']:.1f}  "
          f"%RMSE={m['rmse_pct']:.1f}  bias={m['bias_pct']:+.1f}%")
    for fac in GROUP_ORDER:
        sub = s[s["facility"] == fac]
        mm = metrics(sub); mm.update(set=name, facility=fac); rows.append(mm)
        if mm["n"]:
            print(f"    {fac:<20} n={mm['n']:<4} corr2={mm['corr2']:.3f} medGEH={mm['medGEH']:.1f} "
                  f"%GEH<5={mm['pctGEH5']:.1f} %RMSE={mm['rmse_pct']:.1f} bias={mm['bias_pct']:+.1f}%")


def main():
    vols = nv.load_linkstats()["vol24"].to_dict()   # x10 (flowCap 0.10) full-scale link volumes
    rows = []
    report("HELD-OUT", pd.read_csv(HLD), vols, rows)
    report("CALIBRATION", pd.read_csv(CAL), vols, rows)
    out = pd.DataFrame(rows)[["set", "facility", "n", "corr2", "medGEH", "pctGEH5", "rmse_pct", "bias_pct"]]
    nv.OUTDIR.mkdir(parents=True, exist_ok=True)
    dst = nv.OUTDIR / "summary.csv"
    out.round(3).to_csv(dst, index=False)
    print(f"\nwrote {dst}")
    h = out[(out.facility == "ALL")]
    print("\nHEADLINE (out-of-sample generalisation):")
    for _, r in h.iterrows():
        print(f"  {r['set']:<12} corr2={r['corr2']:.3f}  %GEH<5={r['pctGEH5']:.1f}  %RMSE={r['rmse_pct']:.1f}")


if __name__ == "__main__":
    main()
