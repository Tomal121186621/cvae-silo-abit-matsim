#!/usr/bin/env python3
"""NPMRDS 2023 unsaturated-flow-speed calibration for the BMR MATSim network.

Implements He, Chow, Ozbay et al. Sec 4.2.2, Eqs (9)-(10):

    Freeway  (Eq 9):   f^s_{1,t}   * v0_1     = v^ob_{1,t}
    Arterial (Eq 10):  f^s_{2,t,j} * v0_{2,j} = v^ob_{2,t}      j in {1,2,3}

Steps
  1. Read the RITIS/NPMRDS Massive-Data-Downloader export from data/npmrds_2023/
     (per-TMC epoch speeds + TMC_Identification.csv). Keep weekdays only.
  2. Aggregate to Table 3 : mean observed speed by link type (Freeway=f_system 1-2,
     Arterial=f_system 3-4) x 6 periods.
  3. Read the BMR network -> length-weighted default speed v0 per (type,sub-category).
  4. Factors f = v^ob / v0 (Eqs 9-10). Write speed_factors_2023.csv + observed table.
  5. Apply: write (a) a time-variant NetworkChangeEvents file (6 periods) and
     (b) a static representative-period calibrated network (free-flow = overnight).

If data/npmrds_2023/ has no speed export yet, the script prints the exact RITIS
pull instructions and exits WITHOUT fabricating data (see README_ACCESS.md).

Usage:
  python calibrate_speed_2023.py [--net <network.xml.gz>]
Env: NETVAL_NET overrides the input network.
"""
import sys, gzip, glob, argparse
from pathlib import Path
import numpy as np, pandas as pd

from speed_common import (ROOT, NPMRDS_DIR, SPEED_OUT, MS_TO_MPH, PERIODS,
                          PERIOD_ORDER, HOUR2PERIOD, PERIOD_START_S,
                          parse_car_links, representative_v0, group_key,
                          ARTERIAL_SUB)

DEFAULT_NET = ROOT/"input/network/bmr_network_pt.xml.gz"
SPEED_OUT.mkdir(parents=True, exist_ok=True)

# reasonable bounds so a noisy TMC can't drive a link to absurd free speeds (m/s)
SPEED_FLOOR = {"freeway": 8.9, "arterial": 3.6}     # 20 / 8 mph
SPEED_CEIL  = {"freeway": 33.5, "arterial": 24.6}   # 75 / 55 mph


# ----------------------------------------------------------------- NPMRDS loader
def find_npmrds():
    """Locate the per-TMC speed CSV and the TMC_Identification.csv in NPMRDS_DIR."""
    ident = None
    for cand in ("TMC_Identification.csv", "tmc_identification.csv"):
        p = NPMRDS_DIR/cand
        if p.exists():
            ident = p; break
    # the readings file: any csv with a measurement_tstamp column, not the identification file
    speed = None
    for p in sorted(glob.glob(str(NPMRDS_DIR/"*.csv"))):
        if ident and Path(p).name == ident.name:
            continue
        try:
            head = pd.read_csv(p, nrows=3)
        except Exception:
            continue
        cols = {c.lower() for c in head.columns}
        if "measurement_tstamp" in cols and ("speed" in cols or "average_speed" in cols):
            speed = Path(p); break
    return speed, ident


def load_observed_table3():
    """Return (table3 DataFrame [type x period, mph], n_tmc, n_records) or None."""
    speed_csv, ident_csv = find_npmrds()
    if speed_csv is None or ident_csv is None:
        return None
    ident = pd.read_csv(ident_csv)
    ident.columns = [c.lower() for c in ident.columns]
    tcol = "tmc" if "tmc" in ident.columns else "tmc_code"
    ident[tcol] = ident[tcol].astype(str)
    # f_system 1-2 => Freeway, 3-4 => Arterial (5+ = collector/local, dropped)
    fmap = {1: "freeway", 2: "freeway", 3: "arterial", 4: "arterial"}
    ident["ltype"] = ident["f_system"].map(fmap)
    type_of = dict(zip(ident[tcol], ident["ltype"]))

    df = pd.read_csv(speed_csv)
    df.columns = [c.lower() for c in df.columns]
    scol = "speed" if "speed" in df.columns else "average_speed"
    df["tmc_code"] = df["tmc_code"].astype(str)
    df = df[df[scol].notna() & (df[scol] > 0)].copy()
    ts = pd.to_datetime(df["measurement_tstamp"])
    df = df[ts.dt.dayofweek < 5].copy()                 # weekdays Mon-Fri
    ts = ts[ts.dt.dayofweek < 5]
    df["period"] = ts.dt.hour.map(HOUR2PERIOD)
    df["ltype"]  = df["tmc_code"].map(type_of)
    df = df[df["ltype"].notna()].copy()
    # mean speed per TMC x period, then mean across TMCs (unweighted like the paper's Table 3)
    per_tmc = df.groupby(["ltype", "period", "tmc_code"])[scol].mean().reset_index()
    tab = per_tmc.groupby(["ltype", "period"])[scol].mean().unstack("period")
    tab = tab.reindex(columns=PERIOD_ORDER)
    tab = tab.reindex(index=["freeway", "arterial"])
    return tab, df["tmc_code"].nunique(), len(df)


# ----------------------------------------------------------------- factor build
def build_factors(table3_mph, v0):
    """f = v_ob / v0 per (group, period). Returns tidy DataFrame + wide factor dict."""
    rows = []
    for grp, v0_ms in v0.items():
        ltype = "freeway" if grp == "freeway" else "arterial"
        if ltype not in table3_mph.index:
            continue
        for per in PERIOD_ORDER:
            v_ob_mph = table3_mph.loc[ltype, per]
            if pd.isna(v_ob_mph):
                continue
            v_ob_ms = v_ob_mph / MS_TO_MPH
            f = v_ob_ms / v0_ms
            rows.append({"group": grp, "type": ltype, "period": per,
                         "v0_ms": round(v0_ms, 3), "v0_mph": round(v0_ms*MS_TO_MPH, 2),
                         "obs_speed_mph": round(v_ob_mph, 2),
                         "obs_speed_ms": round(v_ob_ms, 3), "factor": round(f, 4)})
    fac = pd.DataFrame(rows)
    lut = {(r.group, r.period): r.factor for r in fac.itertuples()}
    return fac, lut


# ----------------------------------------------------------------- apply to net
def _calibrated_speed(link, period, lut):
    grp = group_key(link["type"], link["subcat"])
    f = lut.get((grp, period))
    if f is None:
        return None
    v = link["freespeed"] * f
    lo, hi = SPEED_FLOOR[link["type"]], SPEED_CEIL[link["type"]]
    return float(min(max(v, lo), hi))


def write_change_events(links, lut, out_path):
    """Time-variant NetworkChangeEvents: absolute freespeed per link at each period start.

    Requires the run to set timeVariantNetwork=true and inputChangeEventsFile=<out>.
    """
    # one <networkChangeEvent> per (period, rounded-speed) bucket to keep the file small
    from collections import defaultdict
    buckets = defaultdict(list)   # (period, speed_rounded) -> [linkIds]
    n = 0
    for l in links:
        if l["type"] is None:
            continue
        for per in PERIOD_ORDER:
            v = _calibrated_speed(l, per, lut)
            if v is None:
                continue
            buckets[(per, round(v, 3))].append(l["id"]); n += 1
    opn = gzip.open if str(out_path).endswith(".gz") else open
    with opn(out_path, "wt") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<networkChangeEvents xmlns="http://www.matsim.org/files/dtd"\n'
                '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
                '  xsi:schemaLocation="http://www.matsim.org/files/dtd '
                'http://www.matsim.org/files/dtd/networkChangeEvents.xsd">\n')
        for (per, v), lids in sorted(buckets.items(), key=lambda kv: PERIOD_START_S[kv[0][0]]):
            hh = PERIOD_START_S[per]
            t = f"{hh//3600:02d}:{(hh%3600)//60:02d}:00"
            f.write(f'  <networkChangeEvent startTime="{t}">\n')
            for lid in lids:
                f.write(f'    <link refId="{lid}"/>\n')
            f.write(f'    <freespeed type="absolute" value="{v}"/>\n')
            f.write('  </networkChangeEvent>\n')
        f.write('</networkChangeEvents>\n')
    return n, len(buckets)


def write_static_network(net_path, lut, out_path, rep_period="9PM-6AM"):
    """Static representative-period calibrated network (free-flow speed = rep_period).

    Rewrites the freespeed="" of every calibrated car link; all other lines pass through.
    9PM-6AM (least congested) best represents the unsaturated free-flow speed for a
    non-time-variant run; congestion then emerges from the MATSim queue.
    """
    import re
    lid_re = re.compile(r'<link id="([^"]+)"')
    fs_re  = re.compile(r'freespeed="([^"]+)"')
    hwy_re = re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')
    from speed_common import classify
    # need per-link new speed keyed by id; compute in a first streaming pass
    newspeed = {}
    for l in parse_car_links(net_path):
        if l["type"] is None:
            continue
        v = _calibrated_speed(l, rep_period, lut)
        if v is not None:
            newspeed[l["id"]] = v
    opn_in  = gzip.open if str(net_path).endswith(".gz") else open
    opn_out = gzip.open if str(out_path).endswith(".gz") else open
    changed = 0
    with opn_in(net_path, "rt") as fin, opn_out(out_path, "wt") as fout:
        for line in fin:
            m = lid_re.search(line)
            if m and m.group(1) in newspeed and "freespeed=" in line:
                v = newspeed[m.group(1)]
                line = fs_re.sub(f'freespeed="{v}"', line, count=1)
                changed += 1
            fout.write(line)
    return changed


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default=None)
    args = ap.parse_args()
    net = Path(args.net) if args.net else DEFAULT_NET

    print(f"[net] {net}")
    links = list(parse_car_links(net))
    v0 = representative_v0(links)
    print("[v0] length-weighted default free speed per group (mph):")
    for k in sorted(v0):
        print(f"     {k:14s} {v0[k]*MS_TO_MPH:5.1f} mph  ({v0[k]:.2f} m/s)")

    obs = load_observed_table3()
    if obs is None:
        print("\n" + "="*74)
        print("NPMRDS 2023 speed export NOT FOUND in data/npmrds_2023/.")
        print("No data fabricated. Pull it from the RITIS Massive Data Downloader:")
        print("  see data/npmrds_2023/README_ACCESS.md for the exact steps.")
        print("Expected files:")
        print("  data/npmrds_2023/<export>.csv       (tmc_code, measurement_tstamp, speed,...)")
        print("  data/npmrds_2023/TMC_Identification.csv (tmc, f_system, road, miles, ...)")
        print("Re-run this script once they are in place; v0 above is already computed.")
        print("="*74)
        # still emit the v0 reference so the pipeline is inspectable
        pd.DataFrame([{"group": k, "v0_ms": round(v0[k], 3),
                       "v0_mph": round(v0[k]*MS_TO_MPH, 2)} for k in sorted(v0)]
                     ).to_csv(SPEED_OUT/"network_default_speeds_v0.csv", index=False)
        print(f"[write] {SPEED_OUT/'network_default_speeds_v0.csv'}")
        return 2

    table3_mph, n_tmc, n_rec = obs
    print(f"\n[obs] NPMRDS Table 3 (weekday mean speed, mph) — {n_tmc:,} TMCs, {n_rec:,} records")
    print(table3_mph.round(2).to_string())
    table3_mph.round(3).to_csv(SPEED_OUT/"observed_speed_2023.csv")
    print(f"[write] {SPEED_OUT/'observed_speed_2023.csv'}")

    fac, lut = build_factors(table3_mph, v0)
    fac.to_csv(SPEED_OUT/"speed_factors_2023.csv", index=False)
    print(f"[write] {SPEED_OUT/'speed_factors_2023.csv'}  ({len(fac)} rows)")
    print(fac.pivot(index="group", columns="period", values="factor")
             .reindex(columns=PERIOD_ORDER).round(3).to_string())

    # apply -> time-variant change events + static representative network
    ce = ROOT/"input/network/networkChangeEvents_speed_2023.xml.gz"
    n_ce, n_bkt = write_change_events(links, lut, ce)
    print(f"[write] {ce}  ({n_ce:,} link-period settings, {n_bkt} events)")

    stat = ROOT/"input/network/bmr_network_pt_speedcalib_2023.xml.gz"
    n_ch = write_static_network(net, lut, stat)
    print(f"[write] {stat}  ({n_ch:,} car links re-speeded; free-flow=9PM-6AM)")

    print("\n[next] combined re-run options:")
    print("  A) TIME-VARIANT (paper-faithful): set timeVariantNetwork=true and")
    print(f"     inputChangeEventsFile={ce.name} on the base network.")
    print(f"  B) STATIC: run with {stat.name} instead of bmr_network_pt.xml.gz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
