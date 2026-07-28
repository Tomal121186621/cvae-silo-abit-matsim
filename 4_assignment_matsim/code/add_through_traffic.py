#!/usr/bin/env python3
"""Add external-external (through) traffic to the MATSim population via a cordon model — 2023 / ABIT /
corrected-network edition (STEP 2 of the corrected base).

Through-trips have NEITHER end in the BMR — they enter at one freeway/arterial gateway and exit at
another (e.g. I-95 north <-> I-95 south, bypassing downtown / using I-695). They are missing from the
resident ABIT demand (which only has trips with a BMR end), so the interstates/Beltway are under-loaded
(resident-only base_speedfix freeway rel-bias ~ -44%). This injects them.

Method (cordon), UPDATED for 2023:
  1. Gateways + external volumes are PRE-COMPUTED in network_validation_2023/calibration/gateways_2023.csv.
     Each row is a cordon crossing with cx,cy (EPSG:26985, = network CRS), cordon_aadt (2023 boundary AADT),
     cur_vol (resident-modelled volume at that crossing) and `external` = cordon_aadt - cur_vol = the through
     volume that must be added at that gateway (bidirectional veh/day). THROUGH_FRAC is therefore NOT guessed
     any more — the computed `external` column is used directly. Gateways with external<=0 are skipped.
  2. Per gateway split the through volume half-in / half-out: entries = exits = external / 2.
  3. Through O-D between gateways by Furness/IPF: row marginals = entries, col marginals = exits,
     impedance = exp(-beta * beeline).  No A->A.
  4. Generate MATSim through-agents (enter gateway A -> car -> exit gateway B) at the resident SAMPLE rate
     (0.10, matching the 280k 10% ABIT population and qsim flowCap 0.10). Departures are spread by the
     TMAS-2023 weekday hourly profile (network_validation_2023/tmas/station_profiles.csv observed columns;
     falls back to the raw tmas_2023 VOL profile, then a flat profile). Agents are appended to the resident
     ABIT plans -> input/population/bmr_plans_through.xml.gz. At run time MATSim routes the car legs on the
     CORRECTED (freeway-speed-fixed) network, so through-trips load the freeways toward AADT.

Activity type is "other" (a type RunBaltimoreToll registers in the scorer; through_o/through_d would have no
scoring params and crash). Through-agents carry no attributes, so RunBaltimoreToll defaults them to
carAvail=always (autos=1) — fine, modes are fixed and they already have a car leg.
"""
import sys, gzip, math
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GATEWAYS = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
TMAS_PROFILES = ROOT / "network_validation_2023/tmas/station_profiles.csv"   # 2023 observed hourly cols
TMAS_2023_VOL = ROOT / "data/tmas_2023/md_vol"                                # fallback: raw VOL
BASE_POP = ROOT / "scenarios/01_base_no_pricing/input/matsim_population_abit_bmr.xml.gz"  # resident ABIT pop
OUT = ROOT / "input/population/bmr_plans_through.xml.gz"

SAMPLE = 0.10          # match resident 10% sample / qsim flowCap 0.10
GRAVITY_BETA = 2.5e-5  # impedance exp(-beta*metres) (validated cordon-gravity value)
SEED = 20230


def gateways():
    """Return (coords Nx2 EPSG:26985, external veh/day) for cordon gateways with external>0."""
    g = pd.read_csv(GATEWAYS)
    g = g[g["external"] > 0].copy()
    coords = g[["cx", "cy"]].to_numpy(float)
    ext = g["external"].to_numpy(float)
    labels = (g["prefix"].astype(str) + " " + g["road"].astype(str)).tolist()
    return coords, ext, labels


def tmas_hourly_profile():
    """Weekday 24-h share from the 2023 TMAS observed profiles (station_profiles.csv obs_h* columns),
    summed over stations and normalised. Falls back to raw tmas_2023 VOL, then flat."""
    if TMAS_PROFILES.exists():
        df = pd.read_csv(TMAS_PROFILES)
        cols = [f"obs_h{h}" for h in range(24)]
        if all(c in df.columns for c in cols):
            prof = df[cols].to_numpy(float).sum(axis=0)
            if prof.sum() > 0:
                print(f"TMAS-2023 hourly profile from {TMAS_PROFILES.name} ({len(df)} stations)")
                return prof / prof.sum()
    # fallback: raw VOL weekday interstate profile
    if TMAS_2023_VOL.exists():
        prof = np.zeros(24)
        for vf in TMAS_2023_VOL.glob("*.VOL"):
            for l in open(vf, errors="ignore"):
                if len(l) < 140 or l[19] not in "23456":
                    continue
                try:
                    prof += np.array([int(l[20 + i * 5:25 + i * 5]) for i in range(24)], float)
                except Exception:
                    pass
        if prof.sum() > 0:
            print("TMAS-2023 hourly profile from raw tmas_2023 VOL files")
            return prof / prof.sum()
    print("WARNING: no TMAS-2023 profile found -> flat hourly profile")
    return np.full(24, 1.0 / 24)


def furness(P, A, coords, iters=100):
    n = len(P)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dist = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
            D[i, j] = math.exp(-GRAVITY_BETA * dist)
    T = D.copy()
    for _ in range(iters):
        rs = T.sum(1); T = T * (P / np.where(rs == 0, 1, rs))[:, None]
        cs = T.sum(0); T = T * (A / np.where(cs == 0, 1, cs))[None, :]
    return T


def hhmmss(sec):
    sec = int(sec) % (24 * 3600)
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def main():
    coords, ext, labels = gateways()
    entries = ext / 2.0
    exits = ext / 2.0
    print(f"cordon gateways with external>0: {len(coords)}")
    for i, (c, v, lab) in enumerate(zip(coords, ext, labels)):
        print(f"  gw{i:2d}: ({c[0]:.0f},{c[1]:.0f})  external~{v:.0f}/day   {lab}")
    print(f"\ntotal external (bidir veh/day): {ext.sum():,.0f}")

    OD = furness(entries, exits, coords)
    tot = OD.sum()
    print(f"total through-trips/day (full): {tot:,.0f}  -> at {SAMPLE:.0%} sample ~ {tot*SAMPLE:,.0f} agents")

    prof = tmas_hourly_profile()
    cum = np.cumsum(prof)
    rng = np.random.default_rng(SEED)

    # read resident base population, strip its closing tag so we can append
    with gzip.open(BASE_POP, "rt") as f:
        base = f.read()
    base = base.replace("</population>\n", "").replace("</population>", "")

    nid = 0
    with gzip.open(OUT, "wt") as w:
        w.write(base)
        for i in range(len(coords)):
            ox, oy = coords[i]
            for j in range(len(coords)):
                if i == j:
                    continue
                cnt = OD[i, j] * SAMPLE
                k = int(cnt) + (1 if rng.random() < (cnt - int(cnt)) else 0)  # stochastic round
                if k <= 0:
                    continue
                dx, dy = coords[j]
                for _ in range(k):
                    h = int(np.searchsorted(cum, rng.random()))
                    h = min(h, 23)
                    dep = h * 3600 + rng.integers(0, 3600)
                    w.write(f'<person id="thru_{nid}">\n<plan selected="yes">\n')
                    w.write(f'<activity type="other" x="{ox:.1f}" y="{oy:.1f}" end_time="{hhmmss(dep)}"/>\n')
                    w.write('<leg mode="car"/>\n')
                    w.write(f'<activity type="other" x="{dx:.1f}" y="{dy:.1f}"/>\n')
                    w.write('</plan>\n</person>\n')
                    nid += 1
        w.write('</population>\n')

    print(f"\nappended {nid:,} through-agents ({SAMPLE:.0%} sample) -> {OUT}")
    print(f"combined demand written. Through-agent count = {nid:,}")


if __name__ == "__main__":
    main()
