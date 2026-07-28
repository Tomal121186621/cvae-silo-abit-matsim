#!/usr/bin/env python3
"""Station partition for SPSA count calibration (step 3).

Splits the 2023 AADT count stations into a CALIBRATION set (shown to SPSA) and a HELD-OUT validation set
(never shown -> out-of-sample test), so the calibrated network is honestly validated.

CALIBRATION set =
  (a) the 14 radial GATEWAYS (from gateways_2023.csv) -- ALWAYS forced in: the cordon crossings the through
      seed + SPSA gateway scales directly target. Emitted with their boundary links (in_lid/out_lid) and
      cordon_aadt as the observed target; is_gateway=1.
  (b) a FACILITY-STRATIFIED, SPATIALLY-INTERLEAVED ~50% sample of the cleanly-matched count stations. Within
      each facility group (Interstate/Freeway, Principal, Minor, Collector/Local) stations are sorted by a
      coarse spatial grid key and every OTHER one is taken, so calibration and hold-out are geographically
      interleaved (not clustered) -- the hold-out then probes the same corridors the calibration did not see.

HELD-OUT set = every cleanly-matched non-gateway station NOT chosen for calibration.

Ramps are EXCLUDED from calibration (capacity fixed, no ramp calibration) but kept in the hold-out for
reporting. Only cleanly-matched stations (n_links>0, match_quality != no_match) are used.

Outputs:
  network_validation_2023/calibration/spsa_calibration_stations.csv
  network_validation_2023/calibration/spsa_holdout_stations.csv
Columns: LOCATION_ID, facility, obs_AADT, matched_link_ids, n_links, lon, lat, is_gateway, set

Usage:  python select_calibration_stations.py
"""
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AUDIT = ROOT / "network_validation_2023/manual_check/station_link_match_audit.csv"
GATEWAYS = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
OUT_CAL = ROOT / "network_validation_2023/calibration/spsa_calibration_stations.csv"
OUT_HLD = ROOT / "network_validation_2023/calibration/spsa_holdout_stations.csv"

FACILITY_GROUPS = ["Interstate/Freeway", "Principal Arterial", "Minor Arterial", "Collector/Local"]
GRID_M = 5000.0   # spatial interleave cell size for sorting (network CRS metres via lon/lat proxy)
SEED = 20230


def load_stations():
    a = pd.read_csv(AUDIT)
    a = a[(a["n_links"] > 0) & (a["match_quality"] != "no_match")].copy()
    a["matched_link_ids"] = a["matched_link_ids"].astype(str)
    a["obs_AADT"] = pd.to_numeric(a["obs_AADT"], errors="coerce")
    a = a.dropna(subset=["obs_AADT", "lon", "lat"])
    a = a[a["obs_AADT"] > 0]
    return a


def stratified_interleave(cal_pool):
    """~50% per facility, spatially interleaved (sort by coarse grid key, take every other)."""
    cal, hld = [], []
    for fac in FACILITY_GROUPS:
        sub = cal_pool[cal_pool["facility"] == fac].copy()
        if sub.empty:
            continue
        # coarse spatial key so consecutive rows are near each other -> alternating split interleaves space
        gx = (sub["lon"] / GRID_M).round().astype(int)
        gy = (sub["lat"] / GRID_M).round().astype(int)
        sub["_key"] = list(zip(gy, gx, sub["LOCATION_ID"]))
        sub = sub.sort_values("_key").reset_index(drop=True)
        sub["_set"] = ["calibration" if i % 2 == 0 else "holdout" for i in range(len(sub))]
        cal.append(sub[sub["_set"] == "calibration"])
        hld.append(sub[sub["_set"] == "holdout"])
    return pd.concat(cal, ignore_index=True), pd.concat(hld, ignore_index=True)


def gateway_rows():
    g = pd.read_csv(GATEWAYS)
    g = g[g["external"] > 0].reset_index(drop=True)
    rows = []
    for _, r in g.iterrows():
        rows.append({
            "LOCATION_ID": f"GW_{r['prefix']}_{int(r['in_lid'])}",
            "facility": {"motorway": "Interstate/Freeway", "motorway_link": "Interstate/Freeway",
                         "trunk": "Principal Arterial"}.get(r["hwy"], "Principal Arterial"),
            "obs_AADT": float(r["cordon_aadt"]),
            "matched_link_ids": f"{int(r['in_lid'])};{int(r['out_lid'])}",
            "n_links": 2, "lon": float(r["cx"]), "lat": float(r["cy"]),
            "is_gateway": 1, "set": "calibration",
        })
    return pd.DataFrame(rows)


def main():
    a = load_stations()
    keep = ["LOCATION_ID", "facility", "obs_AADT", "matched_link_ids", "n_links", "lon", "lat"]
    # ramps: hold-out only (fixed, not calibrated)
    ramps = a[a["facility"] == "Ramp"][keep].copy()
    ramps["is_gateway"] = 0; ramps["set"] = "holdout"
    # calibratable facilities -> stratified interleave
    pool = a[a["facility"].isin(FACILITY_GROUPS)][keep].copy()
    cal, hld = stratified_interleave(pool)
    cal["is_gateway"] = 0; cal["set"] = "calibration"
    hld["is_gateway"] = 0; hld["set"] = "holdout"

    gw = gateway_rows()

    cal_all = pd.concat([gw, cal[keep + ["is_gateway", "set"]]], ignore_index=True)
    hld_all = pd.concat([hld[keep + ["is_gateway", "set"]], ramps], ignore_index=True)

    OUT_CAL.parent.mkdir(parents=True, exist_ok=True)
    cal_all.to_csv(OUT_CAL, index=False)
    hld_all.to_csv(OUT_HLD, index=False)

    def counts(df, name):
        print(f"\n{name}: {len(df)} rows")
        print(df.groupby(["facility"]).size().reindex(
            ["Interstate/Freeway", "Principal Arterial", "Minor Arterial", "Collector/Local", "Ramp"]
        ).fillna(0).astype(int).to_string())

    print(f"cleanly-matched stations: {len(a)}   ({len(gw)} gateways forced into calibration)")
    counts(cal_all, "CALIBRATION (SPSA sees these)")
    print(f"  of which gateways: {int(cal_all['is_gateway'].sum())}")
    counts(hld_all, "HELD-OUT (never shown to SPSA)")
    print(f"\nwrote {OUT_CAL}")
    print(f"wrote {OUT_HLD}")


if __name__ == "__main__":
    main()
