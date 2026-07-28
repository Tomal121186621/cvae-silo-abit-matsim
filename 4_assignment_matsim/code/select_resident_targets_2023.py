#!/usr/bin/env python3
"""Component 1 of the NYC-style resident-only calibration plan.

Partition all 3,794 AADT-2023 count stations into
  (a) a CALIBRATION set  -- stations whose network volume is dominated by RESIDENT
      trips, i.e. the resident-only MATSim model *can* reproduce them, and
  (b) a held-out VALIDATION set -- everything else (freeways, ramps, through
      corridors, high-commercial, extreme-mismatch, plus a reserved slice of good
      resident stations kept for an honest out-of-sample check).

We DISREGARD through-traffic entirely -- there is no E-E injection in this model.
Through-dominated stations are therefore documented in the held-out set, never
calibrated against.

--------------------------------------------------------------------------------
Ratio / x10 note (confirmed against validate_base_hybrid.py + netval2023_common):
  `model_daily` in aadt_validation_2023_cleaned.csv is ALREADY the x10-expanded
  sample volume -- it sums linkstats `vol24`, and `vol24 = HRS0-24avg * SAMPLE_SCALE`
  with SAMPLE_SCALE=10 (flowCapacityFactor 0.10). validate_base_hybrid.py then uses
  ratio = model_daily / obs_AADT with NO further x10, and the published facility
  agg_ratios (Freeway 0.56 / Principal 0.77 / Minor 0.68 / Collector 0.78) are
  reproduced that way. So the "x10" in the plan is already baked into model_daily;
  here ratio = model_daily / obs_AADT.
--------------------------------------------------------------------------------

Vehicle-class extraction reuses the logic from analyze_resident_validation.py:
  truck = SINGLE_UNIT + COMBINATION_UNIT ; commercial = truck + BUS ;
  comm_frac = commercial / AADT_2023 (per-station, from data/aadt_2023_bmr_REAL.geojson).

Outputs:
  network_validation_2023/calibration/calibration_stations_2023.csv
  network_validation_2023/calibration/validation_holdout_2023.csv
  network_validation_2023/FINAL_FIGURES/calibration/station_partition_map.png
"""
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from netval2023_common import ROOT

# ----------------------------------------------------------------- paths
VAL   = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
GEO   = ROOT/"data/aadt_2023_bmr_REAL.geojson"
GATE  = ROOT/"network_validation_2023/calibration/gateways_2023.csv"
CAPF  = ROOT/"network_validation_2023/transitfix/resident_capture_by_facility.csv"
CNTY  = ROOT/"data/bmr_counties.gpkg"
OUTDIR = ROOT/"network_validation_2023/calibration"
FIGDIR = ROOT/"network_validation_2023/FINAL_FIGURES/calibration"

# ----------------------------------------------------------------- tunables
RESIDENT_FACILITIES = {"Principal Arterial", "Minor Arterial", "Collector/Local"}
RATIO_HI      = 1.5     # above this = over-assigned / bad match
RATIO_LO_MULT = 0.5     # lower bound = RATIO_LO_MULT * facility capture_f
COMM_MAX      = 0.15    # commercial fraction ceiling (skipped where class data absent)
GATE_TF_MIN   = 0.5     # a gateway counts as "through" if external/cordon_aadt >= this
GATE_BUFFER_M = 1500.0  # exclude resident stations within this of a through gateway
HOLDOUT_FRAC  = 0.25    # reserve this share of calibration-quality stations for OOS
HOLDOUT_SEED  = 2023    # deterministic reserve, reproducible across runs

# Through mainlines to keep out of calibration regardless of local match quality.
# Matched on (ID_PREFIX, ID_RTE_NO) -- precise -- plus a ROADNAME keyword net.
THROUGH_ROUTES = {("IS", 95), ("IS", 695), ("IS", 895),
                  ("IS", 97), ("IS", 70), ("IS", 83), ("MD", 295)}
THROUGH_NAME_RE = (r"BELTWAY|KENNEDY|JFK|BALT.*WASH|WASH.*P(?:KW|ARK)|"
                   r"B[-\s]?W\s*P(?:KW|ARK)|HANSON|HARBOR TUNNEL|RITCHIE")


# ----------------------------------------------------------------- load / join
def load():
    v = pd.read_csv(VAL)
    g = gpd.read_file(GEO)[["LOCATION_ID", "AADT_2023", "CAR_AADT", "LIGHT_TRUCK_AADT",
                            "BUS_AADT", "SINGLE_UNIT_AADT", "COMBINATION_UNIT_AADT"]]
    v = v.merge(g, on="LOCATION_ID", how="left")
    # vehicle-class extraction (analyze_resident_validation.py convention)
    truck = v.SINGLE_UNIT_AADT + v.COMBINATION_UNIT_AADT
    comm  = truck + v.BUS_AADT.fillna(0)
    aadt  = v.AADT_2023.where(v.AADT_2023 > 0)          # avoid /0
    v["comm_frac"] = comm / aadt                        # NaN where class data missing
    # capture factor per facility (resident agg ratio)
    cap = pd.read_csv(CAPF).set_index("facility")["agg_ratio"].to_dict()
    v["capture_f"] = v.facility.map(cap)
    # model/obs ratio (model_daily already x10-scaled -- see header)
    v["ratio"] = v.model_daily / v.obs_AADT.where(v.obs_AADT > 0)
    return v, cap


def gateway_flags(v):
    """Distance (m) to the nearest THROUGH gateway (through-fraction >= GATE_TF_MIN)."""
    g = pd.read_csv(GATE)
    g["tf"] = g.external / g.cordon_aadt.where(g.cordon_aadt > 0)
    thru = g[g.tf >= GATE_TF_MIN]
    gx = thru.cx.values[None, :]; gy = thru.cy.values[None, :]   # EPSG:26985 metres
    sx = v.lon.values[:, None];   sy = v.lat.values[:, None]     # station easting/northing
    d = np.sqrt((sx - gx) ** 2 + (sy - gy) ** 2)                 # (n_stn, n_gate)
    return d.min(axis=1), len(thru)


# ----------------------------------------------------------------- classify
def is_through_named(row):
    if (row.ID_PREFIX, int(row.ID_RTE_NO)) in THROUGH_ROUTES:
        return True
    return bool(pd.Series([str(row.ROADNAME)]).str.contains(
        THROUGH_NAME_RE, case=False, regex=True, na=False).iloc[0])


def classify(v):
    dmin, n_thru_gate = gateway_flags(v)
    v = v.copy()
    v["gate_dist_m"] = dmin
    v["near_gateway"] = dmin <= GATE_BUFFER_M
    v["through_named"] = v.apply(is_through_named, axis=1)

    ratio_lo = RATIO_LO_MULT * v.capture_f
    # commercial filter passes when data absent (NaN treated as OK)
    comm_ok = (v.comm_frac <= COMM_MAX) | v.comm_frac.isna()
    ratio_ok = v.ratio.notna() & (v.ratio >= ratio_lo) & (v.ratio <= RATIO_HI)
    fac_ok = v.facility.isin(RESIDENT_FACILITIES)
    not_through = ~(v.near_gateway | v.through_named)

    v["calib_eligible"] = fac_ok & ratio_ok & comm_ok & not_through

    # --- held-out reason (first match wins; only meaningful for non-calibration) ---
    def reason(r):
        if r.facility == "Interstate/Freeway":            return "freeway"
        if r.facility == "Ramp":                          return "ramp"
        if r.near_gateway or r.through_named:             return "through_corridor"
        if pd.notna(r.comm_frac) and r.comm_frac > COMM_MAX:  return "high_commercial"
        if (pd.isna(r.ratio) or r.ratio < RATIO_LO_MULT * r.capture_f
                or r.ratio > RATIO_HI):                   return "extreme_ratio"
        return "resident_heldout"      # passed everything -> good resident station
    v["_reason"] = v.apply(reason, axis=1)

    # --- reserve a deterministic slice of eligible stations for OOS validation ---
    elig = v[v.calib_eligible].copy()
    rng = np.random.RandomState(HOLDOUT_SEED)
    held = set(elig.sample(frac=HOLDOUT_FRAC, random_state=rng).LOCATION_ID)
    v["in_calibration"] = v.calib_eligible & ~v.LOCATION_ID.isin(held)
    # eligible-but-reserved get the resident_heldout tag
    v.loc[v.calib_eligible & v.LOCATION_ID.isin(held), "_reason"] = "resident_heldout"
    return v, n_thru_gate


# ----------------------------------------------------------------- outputs
COLS = ["LOCATION_ID", "facility", "ROADNAME", "obs_AADT", "model_daily",
        "ratio", "capture_f", "comm_frac"]


def write_csvs(v):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    calib = v[v.in_calibration].copy()
    calib["reason"] = "resident_dominated"
    calib[COLS + ["reason"]].to_csv(OUTDIR/"calibration_stations_2023.csv", index=False)

    hold = v[~v.in_calibration].copy()
    hold["holdout_reason"] = hold["_reason"]
    hold[COLS + ["holdout_reason"]].to_csv(OUTDIR/"validation_holdout_2023.csv", index=False)
    return calib, hold


def qa_map(v):
    FIGDIR.mkdir(parents=True, exist_ok=True)
    cty = gpd.read_file(CNTY)
    THRU = {"freeway", "ramp", "through_corridor"}
    BAD  = {"high_commercial", "extreme_ratio"}
    fig, ax = plt.subplots(figsize=(11, 11))
    cty.boundary.plot(ax=ax, color="0.6", lw=0.8, zorder=1)

    def sel(mask):
        d = v[mask]
        return d.lon.values, d.lat.values

    groups = [
        (v.in_calibration,                          "#1a9641", 14, "Calibration (resident-dominated)"),
        (~v.in_calibration & (v._reason == "resident_heldout"), "#2c7fb8", 12, "Held-out resident (OOS check)"),
        (~v.in_calibration & v._reason.isin(BAD),   "#f4a000", 10, "Held-out resident (bad match: comm / ratio)"),
        (~v.in_calibration & v._reason.isin(THRU),  "#d7191c",  9, "Held-out through / freeway / ramp"),
    ]
    for mask, c, s, lab in groups:
        x, y = sel(mask)
        ax.scatter(x, y, s=s, c=c, alpha=0.7, edgecolors="none", zorder=3, label=lab)

    ax.set_title("Resident-model AADT station partition (2023) -- calibration vs held-out",
                 fontsize=13)
    ax.set_aspect("equal"); ax.set_axis_off()
    handles = [Line2D([0], [0], marker="o", ls="", mfc=c, mec="none",
                      ms=8, label=lab) for _, c, _, lab in groups]
    ax.legend(handles=handles, loc="lower left", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(FIGDIR/"station_partition_map.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------- summary
def summarize(v, cap, n_thru_gate):
    calib = v[v.in_calibration]; hold = v[~v.in_calibration]
    print("=" * 78)
    print("COMPONENT 1 -- RESIDENT-MODEL AADT STATION PARTITION (2023)")
    print("=" * 78)
    print(f"total stations               : {len(v):>5}")
    print(f"CALIBRATION (resident)       : {len(calib):>5}")
    print(f"HELD-OUT (validation)        : {len(hold):>5}")
    print(f"through gateways (tf>={GATE_TF_MIN}) used as {GATE_BUFFER_M:.0f} m buffers : {n_thru_gate}")

    print("\ncapture_f by facility (resident agg ratio, calibration lower-bound = 0.5x):")
    for f in ["Principal Arterial", "Minor Arterial", "Collector/Local", "Interstate/Freeway"]:
        if f in cap:
            print(f"   {f:<20} capture_f={cap[f]:.3f}  ratio-band=[{0.5*cap[f]:.2f}, {RATIO_HI:.2f}]")

    print("\nCALIBRATION vs HELD-OUT by facility:")
    tab = (v.assign(grp=np.where(v.in_calibration, "calibration", "held_out"))
             .pivot_table(index="facility", columns="grp", values="LOCATION_ID",
                          aggfunc="count", fill_value=0))
    for c in ("calibration", "held_out"):
        if c not in tab: tab[c] = 0
    tab = tab.reindex(["Principal Arterial", "Minor Arterial", "Collector/Local",
                       "Interstate/Freeway", "Ramp"]).fillna(0).astype(int)
    tab["total"] = tab.calibration + tab.held_out
    print(tab[["calibration", "held_out", "total"]].to_string())

    print("\nHELD-OUT breakdown by reason:")
    rc = hold._reason.value_counts()
    for r in ["resident_heldout", "freeway", "ramp", "through_corridor",
              "high_commercial", "extreme_ratio"]:
        print(f"   {r:<18}: {int(rc.get(r, 0)):>5}")
    n_should = int(rc.get("resident_heldout", 0))
    n_under  = int(rc.get("freeway", 0) + rc.get("ramp", 0) + rc.get("through_corridor", 0))
    print(f"\n   -> resident_heldout (should MATCH out-of-sample)      : {n_should}")
    print(f"   -> through/freeway/ramp (EXPECTED to under-count)     : {n_under}")

    # sanity: the named through mainlines must all be held out
    print("\nSANITY -- through mainlines must be in held-out set:")
    for pref, rte, lab in [("IS", 95, "I-95"), ("IS", 695, "I-695"),
                           ("IS", 895, "I-895"), ("MD", 295, "MD-295")]:
        m = v[(v.ID_PREFIX == pref) & (v.ID_RTE_NO == rte)]
        if len(m):
            nc = int(m.in_calibration.sum())
            print(f"   {lab:<7} n={len(m):>3}  in_calibration={nc}  "
                  f"{'OK (all held out)' if nc == 0 else '!! LEAK'}")
        else:
            print(f"   {lab:<7} (no stations with this prefix/route)")
    nramp = int(v[v.facility == 'Ramp'].in_calibration.sum())
    print(f"   Ramp    in_calibration={nramp}  "
          f"{'OK (all held out)' if nramp == 0 else '!! LEAK'}")

    def examples(mask, n=4):
        d = v[mask][["LOCATION_ID", "facility", "ROADNAME", "obs_AADT",
                     "model_daily", "ratio", "comm_frac"]].head(n)
        return d.to_string(index=False)

    print("\nEXAMPLE calibration stations:")
    print(examples(v.in_calibration))
    print("\nEXAMPLE held-out resident (OOS):")
    print(examples(~v.in_calibration & (v._reason == "resident_heldout")))
    print("\nEXAMPLE held-out through/freeway/ramp:")
    print(examples(~v.in_calibration & v._reason.isin({"freeway", "ramp", "through_corridor"})))


def main():
    v, cap = load()
    v, n_thru_gate = classify(v)
    write_csvs(v)
    qa_map(v)
    summarize(v, cap, n_thru_gate)
    print(f"\nwrote {OUTDIR/'calibration_stations_2023.csv'}")
    print(f"wrote {OUTDIR/'validation_holdout_2023.csv'}")
    print(f"wrote {FIGDIR/'station_partition_map.png'}")


if __name__ == "__main__":
    main()
