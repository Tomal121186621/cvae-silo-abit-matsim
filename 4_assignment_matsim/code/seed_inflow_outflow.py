#!/usr/bin/env python3
"""Non-resident external INFLOW / OUTFLOW car-trip seed for the FULLY-LOADED I-695 network.

Companion to seed_gateway_through_od.py. The through seed handles trips with NEITHER end in the BMR
(gateway -> gateway, bypassing the interior). This seed handles the OTHER half of the external gap:
trips with EXACTLY ONE end at a cordon gateway and the OTHER end at an INTERIOR BMR zone. These load the
RADIAL FREEWAY INTERIORS (I-95, I-83, BW-Pkwy, JFK, ... reaching central Baltimore) which the resident-only
ABIT demand and the gateway<->gateway through seed both under-load.

Cordon-conserving split (marginals preserved, no double counting):
  Each gateway g has external_g bidirectional crossings/day (the cordon gap = cordon_aadt - cur_vol).
  A fraction inflow_frac of that gap is inflow/outflow (the rest stays through, seeded elsewhere).
    inbound  half  external_g/2  -> inflow_g  = external_g/2 * inflow_frac   (gateway -> interior)
    outbound half  external_g/2  -> outflow_g = external_g/2 * inflow_frac   (interior -> gateway)
  Cordon marginals hold because an inflow trip still crosses g INBOUND (its origin sits on in_lid and is
  counted the moment it moves off in_lid) and an outflow trip still crosses g OUTBOUND.

Defect-1 (VehicleLeavesTraffic vs LinkLeaveEvent) handling, mirroring the through seed:
  - INFLOW  origin activity  ON  gateway g's in_lid  (crossing inbound = already counted when it departs);
            destination activity at an INTERIOR zone's nearest car link (interior, no cordon issue).
  - OUTFLOW origin activity  at an interior zone's nearest car link;
            destination activity on the DOWNSTREAM link of g's out_lid (via seed.gateway_downstream_links)
            so out_lid is TRAVERSED (LinkLeaveEvent -> counted), not ended-on (uncounted).

Gravity destination distribution:
  Interior zones (599 BMR zones, EPSG:26985) from interior_zone_attraction.csv. For each gateway g the
  free-flow shortest-path time t(g,z) is dijkstra from g's interior node (in_lid.to for inflow, out_lid.from
  for outflow) to each zone's nearest network node. Weight w(g,z) = attraction_z * exp(-beta * t_gz),
  beta = seed.GRAVITY_BETA_TIME. Inflow_g / outflow_g are distributed across zones proportional to w.

Ids: prefix "ext_io_" (equity post-processing already excludes ext_/frt_; distinct from the through seed's
"ext_" so both seeds can be appended to the same base without id collision). NO subpopulation attribute
(default subpop only; a custom subpop => "No strategy found!" crash). Sample + stochastic rounding + TMAS
departure profile all match the through seed.

Usage (safe sanity check, no plan write, no network load beyond topology+dijkstra):
    python seed_inflow_outflow.py --report-only --inflow-frac 0.5

Production:
    python seed_inflow_outflow.py --inflow-frac 0.5 \
        --base scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v8.xml.gz \
        --out  input/population/bmr_plans_v8_inflow_outflow.xml.gz
"""
import argparse, gzip, json, sys
from pathlib import Path
import numpy as np, pandas as pd

import seed_gateway_through_od as seed   # REUSE its helpers -- do NOT reimplement

INTERIOR = seed.ROOT / "network_validation_2023/calibration/interior_zone_attraction.csv"


# --------------------------------------------------------------------------- interior zones
def load_interior_zones():
    z = pd.read_csv(INTERIOR)
    z = z[z["attraction"] > 0].reset_index(drop=True).copy()
    return z


# --------------------------------------------------------------------------- car graph (single-source)
def build_car_graph():
    """Parse the speedcal CAR network -> (csr adjacency A [seconds], node_idx {node_id: idx}).

    Same graph seed.sptime_cost builds (edge weight = length / freespeed, car links only), but returned
    whole so we can run SINGLE-SOURCE dijkstra from each gateway node to ALL nodes (sptime_cost only keeps
    gateway->gateway pairs)."""
    import re
    from scipy.sparse import csr_matrix

    node_idx = {}
    rows, cols, wts = [], [], []
    nre = re.compile(r'<node id="([^"]+)"')
    lre = re.compile(r'<link id="[^"]+" from="([^"]+)" to="([^"]+)" length="([^"]+)"[^>]*freespeed="([^"]+)"[^>]*modes="([^"]+)"')

    def nid(x):
        if x not in node_idx:
            node_idx[x] = len(node_idx)
        return node_idx[x]

    with gzip.open(seed.NETWORK, "rt") as f:
        for line in f:
            m = nre.search(line)
            if m:
                nid(m.group(1)); continue
            m = lre.search(line)
            if m:
                if "car" not in m.group(5).split(","):
                    continue
                fr, to = nid(m.group(1)), nid(m.group(2))
                length = float(m.group(3)); fs = max(float(m.group(4)), 0.1)
                rows.append(fr); cols.append(to); wts.append(length / fs)   # seconds
    n = len(node_idx)
    A = csr_matrix((wts, (rows, cols)), shape=(n, n))
    print(f"  [graph] car graph: {n:,} nodes, {len(wts):,} directed links", flush=True)
    return A, node_idx


# --------------------------------------------------------------------------- gravity impedance g x zone
def gateway_zone_time(g, zones, link2node, node_xy):
    """t(g,z) free-flow shortest-path seconds from each gateway's interior node to each zone's nearest car
    node. Inflow source = in_lid.to (interior end of the inbound link); outflow source = out_lid.from
    (interior end of the outbound link). Returns (t_in [ng,nz], t_out [ng,nz], zone_node_idx [nz])."""
    from scipy.spatial import cKDTree
    from scipy.sparse.csgraph import dijkstra

    A, node_idx = build_car_graph()

    # zone centroid -> nearest CAR node (restrict KDTree to car-link endpoints so targets are reachable)
    car_nodes = sorted({nd for fr, to in link2node.values() for nd in (fr, to)})
    car_xy = np.array([node_xy[nd] for nd in car_nodes], float)
    ztree = cKDTree(car_xy)
    zc = zones[["coordX", "coordY"]].to_numpy(float)
    _, zn = ztree.query(zc, k=1)
    zone_node_idx = np.array([node_idx[car_nodes[i]] for i in zn], int)   # graph idx of each zone's node

    def _src(lid, end):   # end=1 -> to-node (in_lid), end=0 -> from-node (out_lid)
        lid = str(lid)
        if lid not in link2node:
            return None
        return node_idx.get(link2node[lid][end])

    src_in  = [_src(il, 1) for il in g["in_lid"]]      # inflow  source = in_lid.to
    src_out = [_src(ol, 0) for ol in g["out_lid"]]     # outflow source = out_lid.from
    miss = [g["label"].iloc[i] for i, s in enumerate(src_in) if s is None] + \
           [g["label"].iloc[j] for j, t in enumerate(src_out) if t is None]
    if miss:
        raise SystemExit(f"[gravity] FATAL: gateway link->node unresolved in {seed.NETWORK.name}: {miss} "
                         "(fix in_lid/out_lid or the network path -- do NOT let impedance degrade to uniform)")

    all_src = sorted(set(src_in) | set(src_out))
    dist = dijkstra(A, directed=True, indices=all_src)   # (n_src, n_nodes) seconds
    smap = {s: r for r, s in enumerate(all_src)}

    ng, nz = len(g), len(zones)
    t_in  = np.empty((ng, nz)); t_out = np.empty((ng, nz))
    for i in range(ng):
        t_in[i]  = dist[smap[src_in[i]]][zone_node_idx]
        t_out[i] = dist[smap[src_out[i]]][zone_node_idx]
    # unreachable -> large finite so exp(-beta*t) -> ~0 (never chosen)
    big = 3 * max(np.nanmax(t_in[np.isfinite(t_in)]) if np.isfinite(t_in).any() else 1e4,
                  np.nanmax(t_out[np.isfinite(t_out)]) if np.isfinite(t_out).any() else 1e4)
    t_in[~np.isfinite(t_in)]  = big
    t_out[~np.isfinite(t_out)] = big
    return t_in, t_out, zone_node_idx


def gravity_alloc(vol_g, t_gz, attraction, beta):
    """Distribute each gateway's volume vol_g[i] across zones proportional to attraction * exp(-beta*t).
    Returns [ng, nz] trip matrix (full scale) whose row sums == vol_g."""
    w = attraction[None, :] * np.exp(-beta * t_gz)     # [ng, nz]
    rs = w.sum(1)
    w = w / np.where(rs == 0, 1.0, rs)[:, None]
    return w * vol_g[:, None]


# --------------------------------------------------------------------------- zone -> nearest car link
def zone_nearest_link(zones, link2node, node_xy):
    """Each zone centroid -> nearest CAR link (by link midpoint). Returns (lids [nz], link_xy [nz,2])."""
    from scipy.spatial import cKDTree
    lids = list(link2node.keys())
    mids = np.array([[(node_xy[fr][0] + node_xy[to][0]) / 2.0,
                      (node_xy[fr][1] + node_xy[to][1]) / 2.0]
                     for fr, to in (link2node[l] for l in lids)], float)
    tree = cKDTree(mids)
    zc = zones[["coordX", "coordY"]].to_numpy(float)
    _, idx = tree.query(zc, k=1)
    return [lids[i] for i in idx], mids[idx]


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inflow-frac", type=float, default=0.5,
                    help="fraction of each gateway's external gap that is inflow/outflow (rest is through)")
    ap.add_argument("--base", default=str(seed.V8_POP), help="base plan file to append agents to")
    ap.add_argument("--out", default=str(seed.ROOT / "input/population/bmr_plans_v8_inflow_outflow.xml.gz"))
    ap.add_argument("--sample", type=float, default=seed.SAMPLE)
    ap.add_argument("--impedance", default="sptime", help="free-flow shortest-path time gravity (only mode)")
    ap.add_argument("--scales", default=None, help="JSON list/dict of per-gateway through-scales (SPSA), "
                                                   "applied to external BEFORE the inflow/outflow split")
    ap.add_argument("--beta", type=float, default=None, help="override gravity beta (default seed.GRAVITY_BETA_TIME)")
    ap.add_argument("--report-only", action="store_true", help="compute + print volumes, write NO plan file")
    ap.add_argument("--seed", type=int, default=seed.SEED)
    args = ap.parse_args()

    beta = args.beta if args.beta is not None else seed.GRAVITY_BETA_TIME
    scales = json.loads(args.scales) if args.scales else None

    g = seed.load_gateways(scales)                       # entries = exits = external*scale/2
    zones = load_interior_zones()
    print(f"gateways with external>0: {len(g)}   interior zones: {len(zones)}")
    print(f"inflow_frac = {args.inflow_frac}   beta = {beta:g}   Sum external (bidir) = {g['external'].sum():,.0f}")
    if scales is not None:
        print(f"  applied SPSA scales; scaled Sum external = {(g['external']*g['scale']).sum():,.0f}")

    # cordon-conserving split: inbound half -> inflow, outbound half -> outflow (each * inflow_frac)
    inflow_g  = g["entries"].to_numpy(float) * args.inflow_frac    # gateway -> interior
    outflow_g = g["exits"].to_numpy(float)   * args.inflow_frac    # interior -> gateway

    link2node, node2out, node_xy = seed.load_network_topology()
    t_in, t_out, _ = gateway_zone_time(g, zones, link2node, node_xy)
    attraction = zones["attraction"].to_numpy(float)

    OD_in  = gravity_alloc(inflow_g,  t_in,  attraction, beta)     # [ng, nz] inflow trips gateway i -> zone z
    OD_out = gravity_alloc(outflow_g, t_out, attraction, beta)     # [ng, nz] outflow trips zone z -> gateway i

    tot_in, tot_out = OD_in.sum(), OD_out.sum()
    print(f"\nimpedance = {args.impedance}")
    print(f"total INFLOW  trips/day (full)  = {tot_in:,.0f}")
    print(f"total OUTFLOW trips/day (full)  = {tot_out:,.0f}")
    print(f"total inflow+outflow crossings  = {tot_in+tot_out:,.0f}   "
          f"(= Sum external/2*inflow_frac inbound + same outbound = Sum external*inflow_frac)")
    print(f"expected = Sum external * inflow_frac = {g['external'].sum()*args.inflow_frac*(g['scale'].mean() if scales is None else 1):,.0f}"
          if scales is None else "")
    print(f"at {args.sample:.4g} sample ~ {(tot_in+tot_out)*args.sample:,.0f} inflow/outflow agents")

    # ---- per-gateway table + cordon-conservation check ----
    rep = pd.DataFrame({
        "gateway": g["label"].values,
        "hwy": g["hwy"].values,
        "external_gap": g["external"].round(0).values,
        "inbound_half": (g["entries"]).round(0).values,
        "inflow_g": OD_in.sum(1).round(0),
        "outflow_g": OD_out.sum(1).round(0),
    })
    # cordon conservation: inflow crossings at g inbound must equal external_g/2*inflow_frac
    expect_in = (g["external"].to_numpy(float) * g["scale"].to_numpy(float) / 2.0) * args.inflow_frac
    rep["expect_inbound_cross"] = expect_in.round(0)
    rep["cordon_ok"] = np.isclose(OD_in.sum(1), expect_in, rtol=1e-6, atol=1e-6)
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print("\nper-gateway inflow/outflow (cordon-conserving split):")
        print(rep.to_string(index=False))
    print(f"\ncordon conservation (inflow_g == external_g/2*inflow_frac): "
          f"{'ALL OK' if rep['cordon_ok'].all() else 'MISMATCH'} "
          f"({rep['cordon_ok'].sum()}/{len(rep)} gateways)")

    # ---- sample-gateway top-5 destination zones (sanity: I-95/I-83 -> central Baltimore) ----
    sample_idx = list(np.argsort(-inflow_g)[:2])   # 2 biggest-inflow gateways (typically I-95, BW-Pkwy/I-83)
    gxy = g[["cx", "cy"]].to_numpy(float)
    zc = zones[["coordX", "coordY"]].to_numpy(float)
    zid = zones["zone"].to_numpy()
    for i in sample_idx:
        order = np.argsort(-OD_in[i])[:5]
        print(f"\ntop-5 INFLOW destination zones for gateway '{g['label'].iloc[i]}' (inflow_g={inflow_g[i]:,.0f}):")
        for z in order:
            km = np.hypot(zc[z, 0] - gxy[i, 0], zc[z, 1] - gxy[i, 1]) / 1000.0
            print(f"    zone {int(zid[z]):>4d}   trips/day={OD_in[i, z]:8.1f}   {km:6.1f} km   "
                  f"attraction={attraction[z]:.0f}")

    if args.report_only:
        print("\n--report-only: no plan file written.")
        return

    # ---- write plans: append inflow/outflow agents to the base pop ----
    prof = seed.tmas_profile(); cum = np.cumsum(prof)
    rng = np.random.default_rng(args.seed)
    in_lid = g["in_lid"].astype(str).tolist()

    # outflow destination = one hop DOWNSTREAM of out_lid so out_lid is traversed (LinkLeave -> counted)
    ds_link, ds_node = seed.gateway_downstream_links(g, link2node, node2out)
    n_fb = sum(1 for a, b in zip(ds_link, g["out_lid"].astype(str)) if a == b)
    print(f"  [defect1] outflow dest downstream of out_lid for {len(ds_link)-n_fb}/{len(ds_link)} gateways "
          f"({n_fb} dead-end fallbacks still end on out_lid)", flush=True)

    zlids, zxy = zone_nearest_link(zones, link2node, node_xy)   # each zone's nearest car link + midpoint xy
    gxy = g[["cx", "cy"]].to_numpy(float)

    def _round(cnt):
        return int(cnt) + (1 if rng.random() < (cnt - int(cnt)) else 0)

    def _dep():
        h = min(int(np.searchsorted(cum, rng.random())), 23)
        return h * 3600 + int(rng.integers(0, 3600))

    with gzip.open(args.base, "rt") as f:
        base = f.read()
    base = base.replace("</population>\n", "").replace("</population>", "")

    nid = 0
    outp = Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    ng, nz = len(g), len(zones)
    with gzip.open(outp, "wt") as w:
        w.write(base)
        for i in range(ng):
            ox, oy = gxy[i]                         # gateway centroid (fallback coord for in_lid)
            dlink, dnode = ds_link[i], ds_node[i]   # outflow destination (downstream of out_lid)
            dxy = node_xy.get(dnode) if dnode is not None else None
            dgx, dgy = dxy if dxy else (ox, oy)
            for z in range(nz):
                zl = zlids[z]; zx, zy = zxy[z]
                # INFLOW: origin ON in_lid (crossing inbound = counted) -> interior zone link
                k = _round(OD_in[i, z] * args.sample)
                for _ in range(k):
                    dep = _dep()
                    w.write(f'<person id="ext_io_{nid}">\n')
                    w.write('<plan selected="yes">\n')
                    w.write(f'<activity type="other" link="{in_lid[i]}" x="{ox:.1f}" y="{oy:.1f}" end_time="{seed.hhmmss(dep)}"/>\n')
                    w.write('<leg mode="car"/>\n')
                    w.write(f'<activity type="other" link="{zl}" x="{zx:.1f}" y="{zy:.1f}"/>\n')
                    w.write('</plan>\n</person>\n')
                    nid += 1
                # OUTFLOW: origin at interior zone link -> destination DOWNSTREAM of out_lid (out_lid traversed)
                k = _round(OD_out[i, z] * args.sample)
                for _ in range(k):
                    dep = _dep()
                    w.write(f'<person id="ext_io_{nid}">\n')
                    w.write('<plan selected="yes">\n')
                    w.write(f'<activity type="other" link="{zl}" x="{zx:.1f}" y="{zy:.1f}" end_time="{seed.hhmmss(dep)}"/>\n')
                    w.write('<leg mode="car"/>\n')
                    w.write(f'<activity type="other" link="{dlink}" x="{dgx:.1f}" y="{dgy:.1f}"/>\n')
                    w.write('</plan>\n</person>\n')
                    nid += 1
        w.write('</population>\n')
    print(f"\nappended {nid:,} inflow/outflow agents ({args.sample:.4g} sample) -> {outp}")


if __name__ == "__main__":
    main()
