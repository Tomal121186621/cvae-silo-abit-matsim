#!/usr/bin/env python3
"""External / through-OD seed for the FULLY-LOADED I-695 network (SPSA calibration step 1).

Through-trips have NEITHER end inside the BMR: they enter at one radial gateway and leave at another
(e.g. I-95 N <-> I-95 S bypassing downtown via I-695). They are absent from the resident ABIT demand
(which only has trips with a BMR end), so the freeways / Beltway are under-loaded in the resident-only
base (freeway rel-bias ~ -44%). This script injects them so TOTAL AADT (not just the resident share)
becomes the calibration target.

Method (doubly-constrained gravity / Furness IPF on the gateway x gateway matrix):
  1. Gateways + gaps are PRE-COMPUTED in network_validation_2023/calibration/gateways_2023.csv. Each row
     with external>0 is a radial gateway; external = cordon_aadt - cur_vol = the through veh/day that must
     be added there (bidirectional). cordon_aadt is the TOTAL observed boundary AADT (incl. trucks), so
     the through-OD targets total flow. cur_vol is the resident-modelled volume already at the crossing.
  2. Per gateway split the gap half-in / half-out:  entries = exits = external/2  (optionally x a per-gateway
     SPSA scale factor s_g, see --scales).
  3. Through O-D between gateways by Furness/IPF: row marginals = entries, col marginals = exits (no i->i),
     impedance D_ij = exp(-beta * cost_ij) where cost is:
        --impedance sptime  : network shortest-path FREE-FLOW TRAVEL TIME between the gateways' interior
                              nodes (scipy dijkstra, 14x14). This is the "shortest-path plausibility"
                              weight -- a real I-95 through trip takes the I-95 corridor, so opposite ends
                              of a long freeway are PLAUSIBLE (low travel-time deterrence on that path),
                              unlike a beeline model which penalizes them for being "far".
        --impedance beeline : D_ij = exp(-beta * euclidean_dist) (fast, no network load; used for the
                              lightweight subsample sanity test while a MATSim run holds the RAM).
  4. Emit MATSim through-agents: origin activity ANCHORED ON THE ENTRY BOUNDARY LINK (link=in_lid[i], with
     cx/cy as a fallback coord) -> car leg -> destination activity on the EXIT BOUNDARY LINK (link=out_lid[j]).
     Departures spread by the 2023 TMAS weekday 24-h profile. Agents are generated at the resident SAMPLE
     rate (0.10, matching the 280k 10% ABIT pop and qsim flowCap 0.10) and appended to a base plan file.

Equity note: through-agents get id prefix "ext_" (RunBaltimoreToll keys car-availability off the presence
of a car leg, and equity post-processing filters residents by EXCLUDING id-prefixes ext_/frt_). A
subpopulation="external" attribute is also written (harmless; MATSim just stores it). They carry NO income
attributes -- they are background load, not the equity population.

Usage (subsample sanity test, SAFE while a MATSim run is active -- no network load, no plan write):
    python seed_gateway_through_od.py --impedance beeline --report-only

Production (run when the machine is idle):
    python seed_gateway_through_od.py --impedance sptime \
        --base scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v8.xml.gz \
        --out  input/population/bmr_plans_v8_external.xml.gz
"""
import argparse, gzip, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GATEWAYS = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
NETWORK  = ROOT / "network_validation_2023/network_audit/bmr_network_pt_speedcal_fixed.xml.gz"
TMAS_PROFILES = ROOT / "network_validation_2023/tmas/station_profiles.csv"
V8_POP   = ROOT / "scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v8.xml.gz"
REPORT   = ROOT / "network_validation_2023/calibration/through_od_seed_report.csv"

SAMPLE = 0.10           # resident 10% sample / qsim flowCap 0.10
GRAVITY_BETA_DIST = 2.5e-5    # exp(-beta * metres)   (validated cordon-gravity value)
import os
GRAVITY_BETA_TIME = float(os.environ.get("THROUGH_BETA", "8.0e-4"))  # exp(-beta*sec); 2e-4 keeps long-haul through viable
SEED = 20230


# --------------------------------------------------------------------------- gateway table
def load_gateways(scales=None):
    """Gateways with external>0. Returns a DataFrame with entries/exits (optionally SPSA-scaled)."""
    g = pd.read_csv(GATEWAYS)
    g = g[g["external"] > 0].reset_index(drop=True).copy()
    g["label"] = g["prefix"].astype(str) + " " + g["road"].astype(str).str.slice(0, 40)
    scale = np.ones(len(g))
    if scales is not None:
        # scales: list/array aligned to the external>0 rows, or a {row_index: factor} dict
        if isinstance(scales, dict):
            for k, v in scales.items():
                scale[int(k)] = float(v)
        else:
            s = np.asarray(scales, float)
            scale[: len(s)] = s
    g["scale"] = scale
    g["entries"] = g["external"] * g["scale"] / 2.0
    g["exits"]   = g["external"] * g["scale"] / 2.0
    return g


# --------------------------------------------------------------------------- impedance
def beeline_cost(g):
    xy = g[["cx", "cy"]].to_numpy(float)
    n = len(xy)
    C = np.zeros((n, n))
    for i in range(n):
        C[i] = np.hypot(xy[:, 0] - xy[i, 0], xy[:, 1] - xy[i, 1])
    return C


def load_network_topology():
    """Parse the speedcal CAR network -> (link2node, node2out, node_xy).
      link2node: link_id -> (from_node, to_node)          [car links]
      node2out:  node_id -> [(link_id, to_node), ...]      outgoing car links
      node_xy:   node_id -> (x, y)
    Uses the SAME network the seed/MATSim route on (NETWORK), so link ids and node ids are consistent --
    this is the authoritative topology (the gateways_2023.csv in_tnode/out_fnode were parsed from a DIFFERENT
    network (output_network.xml.gz) whose node numbering does not match, which silently broke sptime)."""
    import re
    node_xy, link2node, node2out = {}, {}, {}
    nre = re.compile(r'<node id="([^"]+)"[^>]*?x="([^"]+)"[^>]*?y="([^"]+)"')
    lre = re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)"')
    mre = re.compile(r'modes="([^"]+)"')
    with gzip.open(NETWORK, "rt") as f:
        for line in f:
            m = nre.search(line)
            if m:
                node_xy[m.group(1)] = (float(m.group(2)), float(m.group(3))); continue
            m = lre.search(line)
            if m:
                mm = mre.search(line)
                if not mm or "car" not in mm.group(1).split(","):
                    continue
                lid, fr, to = m.group(1), m.group(2), m.group(3)
                link2node[lid] = (fr, to)
                node2out.setdefault(fr, []).append((lid, to))
    return link2node, node2out, node_xy


def gateway_downstream_links(g, link2node, node2out):
    """Defect-1 fix: the destination activity must sit ONE HOP DOWNSTREAM (outside) of each gateway's
    out_lid, so the through-vehicle fully TRAVERSES out_lid (emitting a LinkLeaveEvent that linkstats counts)
    instead of ENDING on it (which emits only a VehicleLeavesTrafficEvent -> uncounted outbound crossing).
    out_lid points outward (from=inside, to=outside); a downstream link is any car link leaving out_lid's
    outside node that is not the immediate U-turn back inside. Returns per-gateway (link_id, (x,y)); falls
    back to out_lid itself (with a warning) if the network truly dead-ends at the cordon."""
    ds_link, ds_xy, n_fallback = [], [], 0
    _, node_xy = None, None
    for ol in g["out_lid"].astype(str):
        chosen = None
        if ol in link2node:
            inside, outside = link2node[ol]
            for lid2, to2 in node2out.get(outside, []):
                if to2 == inside:            # skip immediate U-turn back across the cordon
                    continue
                chosen = (lid2, to2); break
        ds_link.append(chosen[0] if chosen else ol)
        ds_xy.append(chosen[1] if chosen else None)
    return ds_link, ds_xy


def sptime_cost(g):
    """14x14 shortest-path FREE-FLOW travel time (s) between gateway interior nodes, via scipy dijkstra.

    Route from each gateway's inbound interior node (in_tnode) to every gateway's outbound interior node
    (out_fnode) on the directed car graph (edge weight = length / freespeed)."""
    import re
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra

    node_idx = {}
    rows, cols, wts = [], [], []
    nre = re.compile(r'<node id="([^"]+)"')
    lre = re.compile(r'<link id="[^"]+" from="([^"]+)" to="([^"]+)" length="([^"]+)"[^>]*freespeed="([^"]+)"[^>]*modes="([^"]+)"')

    def nid(x):
        if x not in node_idx:
            node_idx[x] = len(node_idx)
        return node_idx[x]

    with gzip.open(NETWORK, "rt") as f:
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
    print(f"  [sptime] car graph: {n:,} nodes, {len(wts):,} directed links", flush=True)

    # Resolve gateway routing nodes from the LINK ids (valid in this network), NOT the CSV in_tnode/out_fnode
    # (those came from a different network and don't resolve -> Defect 2). Route the through movement from the
    # interior end of the inbound link (in_lid.to) to the interior end of the outbound link (out_lid.from).
    link2node, _, _ = load_network_topology()
    def _src(il):
        il = str(il); return node_idx.get(link2node[il][1]) if il in link2node else None
    def _tgt(ol):
        ol = str(ol); return node_idx.get(link2node[ol][0]) if ol in link2node else None
    src = [_src(il) for il in g["in_lid"]]
    tgt = [_tgt(ol) for ol in g["out_lid"]]
    miss = [g["label"].iloc[i] for i, s in enumerate(src) if s is None] + \
           [g["label"].iloc[j] for j, t in enumerate(tgt) if t is None]
    if miss:
        raise SystemExit(f"[sptime] FATAL: gateway link->node unresolved in {NETWORK.name}: {miss} "
                         "(fix in_lid/out_lid or the network path -- do NOT let impedance degrade to uniform)")
    valid_src = [s for s in src if s is not None]
    dist = dijkstra(A, directed=True, indices=valid_src)   # (n_src, n) seconds
    smap = {s: r for r, s in enumerate(valid_src)}
    ng = len(g)
    C = np.full((ng, ng), np.inf)
    for i in range(ng):
        if src[i] is None:
            continue
        row = dist[smap[src[i]]]
        for j in range(ng):
            if tgt[j] is None:
                continue
            C[i, j] = row[tgt[j]]
    # any unreachable / self -> large finite so exp() -> ~0 (never chosen), diagonal handled in furness
    big = np.nanmax(C[np.isfinite(C)]) if np.isfinite(C).any() else 1e4
    C[~np.isfinite(C)] = big * 3
    return C


# --------------------------------------------------------------------------- Furness / IPF
def furness(entries, exits, cost, beta, iters=200):
    n = len(entries)
    D = np.exp(-beta * cost)
    np.fill_diagonal(D, 0.0)      # no gateway -> itself
    T = D.copy()
    for _ in range(iters):
        rs = T.sum(1); T = T * (entries / np.where(rs == 0, 1, rs))[:, None]
        cs = T.sum(0); T = T * (exits / np.where(cs == 0, 1, cs))[None, :]
    return T


# --------------------------------------------------------------------------- TMAS departure profile
def tmas_profile():
    if TMAS_PROFILES.exists():
        df = pd.read_csv(TMAS_PROFILES)
        cols = [f"obs_h{h}" for h in range(24)]
        if all(c in df.columns for c in cols):
            prof = df[cols].to_numpy(float).sum(0)
            if prof.sum() > 0:
                return prof / prof.sum()
    print("  WARNING: no TMAS profile -> flat 24-h", flush=True)
    return np.full(24, 1.0 / 24)


def hhmmss(sec):
    sec = int(sec) % (24 * 3600)
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


# --------------------------------------------------------------------------- reconstruction report
def reconstruction_report(g, OD):
    row = OD.sum(1); col = OD.sum(0)              # entries / exits actually realised by Furness
    rep = pd.DataFrame({
        "gateway": g["label"],
        "hwy": g["hwy"],
        "cordon_aadt": g["cordon_aadt"].round(0),
        "cur_vol_resident": g["cur_vol"].round(0),
        "external_gap": g["external"].round(0),
        "seeded_in": row.round(0),
        "seeded_out": col.round(0),
        "seeded_through": (row + col).round(0),
        "reconstructed_total": (row + col + g["cur_vol"]).round(0),   # ~ cordon_aadt
    })
    rep["recon_err_pct"] = (100 * (rep["reconstructed_total"] - rep["cordon_aadt"])
                            / rep["cordon_aadt"].replace(0, np.nan)).round(2)
    return rep


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impedance", choices=["sptime", "beeline"], default="sptime")
    ap.add_argument("--base", default=str(V8_POP), help="base plan file to append external agents to")
    ap.add_argument("--out", default=str(ROOT / "input/population/bmr_plans_v8_external.xml.gz"))
    ap.add_argument("--scales", default=None, help="JSON list/dict of per-gateway scale factors (SPSA)")
    ap.add_argument("--report-only", action="store_true", help="compute OD + report, do NOT write plans")
    ap.add_argument("--sample", type=float, default=SAMPLE)
    ap.add_argument("--through-frac", type=float, default=1.0,
                    help="fraction of each gateway's external that is THROUGH (gateway->gateway). The "
                         "remainder (1-through_frac) is seeded as inflow/outflow by seed_inflow_outflow.py. "
                         "Together they conserve each gateway's cordon marginal.")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    scales = json.loads(args.scales) if args.scales else None
    g = load_gateways(scales)
    print(f"gateways with external>0: {len(g)}   Sum external (bidir veh/day) = {g['external'].sum():,.0f}")
    if scales is not None:
        print(f"  applied SPSA scales; scaled Sum external = {(g['external']*g['scale']).sum():,.0f}")

    cost = sptime_cost(g) if args.impedance == "sptime" else beeline_cost(g)
    beta = GRAVITY_BETA_TIME if args.impedance == "sptime" else GRAVITY_BETA_DIST
    OD = furness(g["entries"].to_numpy(), g["exits"].to_numpy(), cost, beta)

    tot = OD.sum()                                  # through-TRIPS (each trip enters 1 gateway, exits another)
    crossings = 2 * tot                             # gateway CROSSINGS (in + out) -- comparable to bidir gap
    gap = (g["external"] * g["scale"]).sum()        # aggregate bidirectional gateway gap (in + out)
    print(f"\nimpedance = {args.impedance}")
    print(f"total seeded through-TRIPS/day (full)                = {tot:,.0f}")
    print(f"total seeded gateway CROSSINGS (in+out) = 2*trips    = {crossings:,.0f}")
    print(f"aggregate gateway gap (Sum scaled external, bidir)   = {gap:,.0f}")
    print(f"seeded crossings / gap                               = {crossings/gap:.4f}   "
          f"(=1.0: Furness conserves the gateway marginals -- each gateway's in+out = its scaled external)")
    print(f"at {args.sample:.0%} sample ~ {tot*args.sample:,.0f} external agents")

    rep = reconstruction_report(g, OD)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(REPORT, index=False)
    print(f"\nper-gateway reconstruction (seeded_through + cur_vol ~ cordon_aadt) -> {REPORT}")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(rep.to_string(index=False))
    print(f"\nmax |recon_err_pct| = {rep['recon_err_pct'].abs().max():.2f}%  "
          f"(should be ~0: Furness reproduces the gateway marginals)")

    if args.report_only:
        print("\n--report-only: no plan file written.")
        return

    # ---- write plans: append external agents to the base pop ----
    prof = tmas_profile(); cum = np.cumsum(prof)
    rng = np.random.default_rng(args.seed)
    coords = g[["cx", "cy"]].to_numpy(float)
    in_lid = g["in_lid"].astype(str).tolist()
    out_lid = g["out_lid"].astype(str).tolist()
    # Defect-1 fix: destination one hop DOWNSTREAM of out_lid so out_lid is traversed (LinkLeave -> counted).
    link2node, node2out, node_xy = load_network_topology()
    ds_link, ds_node = gateway_downstream_links(g, link2node, node2out)
    n_fb = sum(1 for a, b in zip(ds_link, out_lid) if a == b)
    print(f"  [defect1] destination placed downstream of out_lid for {len(ds_link)-n_fb}/{len(ds_link)} "
          f"gateways ({n_fb} dead-end fallbacks still end on out_lid)", flush=True)

    with gzip.open(args.base, "rt") as f:
        base = f.read()
    base = base.replace("</population>\n", "").replace("</population>", "")

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
                cnt = OD[i, j] * args.through_frac * args.sample
                k = int(cnt) + (1 if rng.random() < (cnt - int(cnt)) else 0)
                if k <= 0:
                    continue
                dl = ds_link[j]
                dxy = node_xy.get(ds_node[j]) if ds_node[j] is not None else None
                dx, dy = dxy if dxy else (coords[j][0], coords[j][1])
                for _ in range(k):
                    h = min(int(np.searchsorted(cum, rng.random())), 23)
                    dep = h * 3600 + int(rng.integers(0, 3600))
                    w.write(f'<person id="ext_{nid}">\n')
                    # NO subpopulation attribute: RunBaltimoreToll registers replanning strategies only for
                    # the DEFAULT subpopulation, so a "subpopulation=external" tag => "No strategy found!" crash.
                    # These agents fall into the default subpop (ReRoute + TimeAllocMutator + ChangeExpBeta,
                    # modes fixed). The operative equity filter is the id prefix "ext_", not this attribute.
                    w.write('<plan selected="yes">\n')
                    w.write(f'<activity type="other" link="{in_lid[i]}" x="{ox:.1f}" y="{oy:.1f}" end_time="{hhmmss(dep)}"/>\n')
                    w.write('<leg mode="car"/>\n')
                    # destination = downstream of out_lid[j] so the vehicle traverses out_lid[j] (counted)
                    w.write(f'<activity type="other" link="{dl}" x="{dx:.1f}" y="{dy:.1f}"/>\n')
                    w.write('</plan>\n</person>\n')
                    nid += 1
        w.write('</population>\n')
    print(f"\nappended {nid:,} external agents ({args.sample:.0%} sample) -> {outp}")


if __name__ == "__main__":
    main()
