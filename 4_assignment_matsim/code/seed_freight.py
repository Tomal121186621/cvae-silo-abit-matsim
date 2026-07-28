#!/usr/bin/env python3
"""Freight / commercial background layer for the fully-loaded I-695 network (SPSA calibration step 2).

WHY a separate layer. The gateway `cordon_aadt` is the TOTAL observed boundary AADT and already INCLUDES
trucks, so the through-OD seed (seed_gateway_through_od.py) already carries freight *as vehicle counts* --
one truck = one vehicle in the AADT target. What that seed does NOT capture is the extra ROAD SPACE a
truck consumes: in congestion a heavy truck behaves like ~2 passenger cars (PCE ~ 2.0). On the truck-heavy
freeway corridors (I-95 / I-70 / I-695, ~6-9% trucks per MDOT vehicle-class data; cf. gap_decomposition.csv
freeway commercial ~6%) that under-states congestion. This layer adds the freight PCE *uplift* as extra
background car-equivalent through-trips so the freeways congest realistically.

Method (simple, documented, background):
  freight_extra_veh_g = external_g * truck_frac_g * (PCE - 1)          # PCE = 2.0  -> uplift = 1x truck vol
Distributed gateway->gateway with the SAME doubly-constrained Furness as the through-OD (same impedance),
emitted as car agents with id prefix "frt_" and subpopulation="freight". They are BACKGROUND (no income,
not the equity population; equity post-processing excludes id-prefixes ext_/frt_). Because cordon_aadt
already counts the trucks themselves, this uplift is deliberately EXTRA vehicles on top of the count target
-- its purpose is congestion realism, not to change the vehicle-count AADT. Keep PCE modest and documented;
set --pce 1.0 to disable the layer entirely (freight then represented only as its vehicle count in the seed).

Usage (subsample sanity, SAFE while a run is active):
    python seed_freight.py --impedance beeline --report-only
Production:
    python seed_freight.py --impedance sptime \
        --base input/population/bmr_plans_v8_external.xml.gz \
        --out  input/population/bmr_plans_v8_external_freight.xml.gz
"""
import argparse, gzip, json
from pathlib import Path
import numpy as np, pandas as pd

# reuse the through-OD machinery so impedance / Furness / TMAS profile stay identical
import seed_gateway_through_od as seed

ROOT = seed.ROOT
FREPORT = ROOT / "network_validation_2023/calibration/freight_seed_report.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impedance", choices=["sptime", "beeline"], default="sptime")
    ap.add_argument("--pce", type=float, default=2.0, help="passenger-car-equivalent per truck (1.0 disables)")
    ap.add_argument("--base", default=str(ROOT / "input/population/bmr_plans_v8_external.xml.gz"))
    ap.add_argument("--out", default=str(ROOT / "input/population/bmr_plans_v8_external_freight.xml.gz"))
    ap.add_argument("--scales", default=None, help="JSON per-gateway scales (SPSA; same as the through seed)")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--sample", type=float, default=seed.SAMPLE)
    ap.add_argument("--seed", type=int, default=seed.SEED + 1)
    args = ap.parse_args()

    scales = json.loads(args.scales) if args.scales else None
    g = seed.load_gateways(scales)
    uplift = (args.pce - 1.0)
    # freight PCE-uplift veh/day per gateway (bidirectional), split half in / half out for Furness
    g["freight_extra"] = g["external"] * g["scale"] * g["truck_frac"] * uplift
    g["entries"] = g["freight_extra"] / 2.0
    g["exits"]   = g["freight_extra"] / 2.0

    print(f"freight PCE = {args.pce}  (uplift factor {uplift:.2f} x truck volume)")
    print(f"gateways: {len(g)}   Sum freight PCE-uplift veh/day = {g['freight_extra'].sum():,.0f}")
    if uplift <= 0:
        print("PCE<=1 -> freight layer disabled (freight represented as vehicle count in the through seed).")
        return

    cost = seed.sptime_cost(g) if args.impedance == "sptime" else seed.beeline_cost(g)
    beta = seed.GRAVITY_BETA_TIME if args.impedance == "sptime" else seed.GRAVITY_BETA_DIST
    OD = seed.furness(g["entries"].to_numpy(), g["exits"].to_numpy(), cost, beta)
    tot = OD.sum()
    print(f"impedance = {args.impedance}   total freight PCE-uplift trips/day = {tot:,.0f}  "
          f"(~ {tot*args.sample:,.0f} agents at {args.sample:.0%})")

    rep = pd.DataFrame({
        "gateway": g["label"], "hwy": g["hwy"], "truck_frac": g["truck_frac"].round(4),
        "external_gap": g["external"].round(0),
        "freight_pce_uplift": g["freight_extra"].round(0),
        "seeded_freight": (OD.sum(1) + OD.sum(0)).round(0),
    })
    FREPORT.parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(FREPORT, index=False)
    print(f"\nfreight per-gateway report -> {FREPORT}")
    with pd.option_context("display.width", 200, "display.max_columns", 12):
        print(rep.to_string(index=False))
    # cross-check freeway share
    frw = g[g["hwy"].isin(["motorway", "motorway_link"])]
    if len(frw):
        share = (frw["external"] * frw["truck_frac"]).sum() / max(frw["external"].sum(), 1)
        print(f"\nfreeway truck share (vol-weighted) = {share:.1%}  (cf. gap_decomposition freeway commercial ~6%)")

    if args.report_only:
        print("\n--report-only: no plan file written.")
        return

    # ---- append freight agents to the (external-augmented) base pop ----
    prof = seed.tmas_profile(); cum = np.cumsum(prof)
    rng = np.random.default_rng(args.seed)
    coords = g[["cx", "cy"]].to_numpy(float)
    in_lid = g["in_lid"].astype(str).tolist(); out_lid = g["out_lid"].astype(str).tolist()
    with gzip.open(args.base, "rt") as f:
        base = f.read()
    base = base.replace("</population>\n", "").replace("</population>", "")
    # Defect-1 fix (same as through seed): destination one hop downstream of out_lid so it is traversed/counted.
    link2node, node2out, node_xy = seed.load_network_topology()
    ds_link, ds_node = seed.gateway_downstream_links(g, link2node, node2out)
    nid = 0
    outp = Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(outp, "wt") as w:
        w.write(base)
        ng = len(g)
        for i in range(ng):
            ox, oy = coords[i]
            for j in range(ng):
                if i == j:
                    continue
                cnt = OD[i, j] * args.sample
                k = int(cnt) + (1 if rng.random() < (cnt - int(cnt)) else 0)
                if k <= 0:
                    continue
                dl = ds_link[j]
                dxy = node_xy.get(ds_node[j]) if ds_node[j] is not None else None
                dx, dy = dxy if dxy else (coords[j][0], coords[j][1])
                for _ in range(k):
                    h = min(int(np.searchsorted(cum, rng.random())), 23)
                    dep = h * 3600 + int(rng.integers(0, 3600))
                    w.write(f'<person id="frt_{nid}">\n')
                    # NO subpopulation attribute (would crash MATSim: no strategy registered for a "freight"
                    # subpop). Freight fall into the default subpop; the operative filter is the id prefix "frt_".
                    w.write('<plan selected="yes">\n')
                    w.write(f'<activity type="other" link="{in_lid[i]}" x="{ox:.1f}" y="{oy:.1f}" end_time="{seed.hhmmss(dep)}"/>\n')
                    w.write('<leg mode="car"/>\n')
                    # destination = downstream of out_lid[j] so the vehicle traverses out_lid[j] (counted)
                    w.write(f'<activity type="other" link="{dl}" x="{dx:.1f}" y="{dy:.1f}"/>\n')
                    w.write('</plan>\n</person>\n')
                    nid += 1
        w.write('</population>\n')
    print(f"\nappended {nid:,} freight agents ({args.sample:.0%} sample) -> {outp}")


if __name__ == "__main__":
    main()
