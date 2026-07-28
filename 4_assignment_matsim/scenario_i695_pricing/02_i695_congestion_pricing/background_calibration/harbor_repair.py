#!/usr/bin/env python3
"""Targeted harbor-crossing repair (path b: constraint-based, all purposes).

Phase identify: find every resident whose selected plan routes over a harbor crossing,
  their far-side activities (home->activity segment intersects the harbor line), and a
  same-side donor location per far-side activity (same type, distance-matched from the
  non-crossing population). Writes candidates.csv (one row per person: crossing legs,
  moves as JSON). Target-independent.

Phase apply --excess N: randomly selects candidates until their crossing legs (x10)
  reach N; rewrites the plans keeping only the selected plan for movers, replacing
  far-side activity coords, dropping stale link refs and routes on adjacent legs.

Usage:
  python3 harbor_repair.py identify
  python3 harbor_repair.py apply --excess 150000 --out plans_resident_repaired.xml.gz
"""
import gzip, json, re, sys
import numpy as np
from pathlib import Path

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
BG = ROOT / "scenarios/02_i695_congestion_pricing/background_calibration"
PLANS = ROOT / "scenarios/01_base_no_pricing/output_calib_fs/pass7/output_plans.xml.gz"
HARBOR = {"53478", "41878", "355067", "373985", "373989", "236094", "keybridge_eb", "keybridge_wb"}
# harbor water line (screenline A geometry, EPSG:26985)
Q1, Q2 = (434500.0, 177500.0), (444500.0, 171500.0)
SEED = 42

def seg_cross(p1, p2, q1=Q1, q2=Q2):
    def ccw(a, b, c): return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return ccw(p1, q1, q2) != ccw(p2, q1, q2) and ccw(p1, p2, q1) != ccw(p1, p2, q2)

re_person = re.compile(r'<person id="([^"]+)"')
re_act = re.compile(r'<activity[^>]*type="([^"]+)"[^>]*x="([0-9.\-]+)" y="([0-9.\-]+)"')

def scan(collect_pools=False):
    """Yield (pid, acts, crossing_leg_idx) per selected plan; optionally build donor pools."""
    pools = {} if collect_pools else None
    with gzip.open(PLANS, "rt") as f:
        pid = None; in_sel = False; acts = []; legidx = -1; crossing = []
        for line in f:
            m = re_person.search(line)
            if m: pid = m.group(1); continue
            if "<plan" in line:
                in_sel = 'selected="yes"' in line; acts = []; legidx = -1; crossing = []
                continue
            if not in_sel: continue
            if "</plan>" in line:
                yield pid, acts, crossing
                in_sel = False; continue
            m = re_act.search(line)
            if m:
                acts.append((m.group(1), float(m.group(2)), float(m.group(3)))); continue
            if "<leg" in line: legidx += 1; continue
            if "<route" in line:
                content = re.sub(r"<[^>]*>", " ", line)
                if any(t in HARBOR for t in content.split()):
                    if legidx not in crossing: crossing.append(legidx)

def identify():
    rng = np.random.default_rng(SEED)
    # pass 1: donor pools from ALL activities (type -> coords array)
    pools = {}
    cand_rows = []
    for pid, acts, crossing in scan():
        if not acts: continue
        for t, x, y in acts:
            pools.setdefault(t, []).append((x, y))
        if not crossing: continue
        home = next(((x, y) for t, x, y in acts if t == "home"), (acts[0][1], acts[0][2]))
        far = [i for i, (t, x, y) in enumerate(acts)
               if t != "home" and seg_cross(home, (x, y))]
        if not far: continue
        cand_rows.append((pid, len(crossing), home, far, [acts[i] for i in far]))
    print(f"crossing persons with far-side activities: {len(cand_rows):,}", flush=True)
    for t in pools: pools[t] = np.array(pools[t])

    # donor match: same type, home-side (segment does not cross), distance-matched
    out = []
    for pid, nlegs, home, far_idx, far_acts in cand_rows:
        moves = {}
        ok = True
        for i, (t, x, y) in zip(far_idx, far_acts):
            P = pools.get(t)
            if P is None or len(P) < 50: ok = False; break
            d0 = np.hypot(x - home[0], y - home[1])
            for attempt in range(6):
                sel = P[np.random.default_rng(abs(hash((pid, i, attempt))) % 2**31).integers(0, len(P), 400)]
                nc = [p for p in sel if not seg_cross(home, (p[0], p[1]))]
                if nc: break
            if not nc: ok = False; break
            nc = np.array(nc)
            j = np.argmin(np.abs(np.hypot(nc[:, 0]-home[0], nc[:, 1]-home[1]) - d0))
            moves[i] = (float(nc[j, 0]), float(nc[j, 1]))
        if ok and moves:
            out.append({"pid": pid, "legs": nlegs, "moves": moves})
    rng.shuffle(out)
    with open(BG / "harbor_repair_candidates.json", "w") as f:
        json.dump(out, f)
    print(f"candidates written: {len(out):,} persons, {sum(c['legs'] for c in out)*10:,} crossing legs/day available")

def apply(excess, outpath):
    cands = json.load(open(BG / "harbor_repair_candidates.json"))
    sel = {}; acc = 0
    for c in cands:
        if acc >= excess / 10.0: break
        sel[c["pid"]] = {int(k): v for k, v in c["moves"].items()}
        acc += c["legs"]
    print(f"selected {len(sel):,} movers covering {acc*10:,.0f} crossing legs/day (target {excess:,})")
    re_x = re.compile(r'x="[0-9.\-]+" y="[0-9.\-]+"')
    re_link = re.compile(r'\s*link="[^"]*"')
    win = gzip.open(PLANS, "rt"); wout = gzip.open(outpath, "wt")
    pid = None; mover = None; in_sel = False; plans_skipping = False
    ai = -1; drop_route_next_leg = False; in_dropped_leg = False; pending_leg_lines = []
    moved_prev = False
    for line in win:
        m = re_person.search(line)
        if m:
            pid = m.group(1); mover = sel.get(pid); ai = -1; moved_prev = False
        if mover is not None:
            if "<plan" in line and 'selected="yes"' not in line:
                plans_skipping = True; continue
            if plans_skipping:
                if "</plan>" in line: plans_skipping = False
                continue
            if "<activity" in line:
                ai += 1
                if ai in mover:
                    x, y = mover[ai]
                    line = re_x.sub(f'x="{x:.1f}" y="{y:.1f}"', line, count=1)
                    line = re_link.sub("", line)
                    moved_prev = True
                else:
                    moved_prev = False
            # drop routes adjacent to moved activities: simplest — drop ALL routes for movers
            if "<route" in line:
                if "</route>" in line or "/>" in line: continue
                in_dropped_leg = True; continue
            if in_dropped_leg:
                if "</route>" in line: in_dropped_leg = False
                continue
        wout.write(line)
    win.close(); wout.close()
    print(f"wrote {outpath}")

if __name__ == "__main__":
    if sys.argv[1] == "identify": identify()
    else:
        import argparse
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--excess", type=int, required=True)
        ap.add_argument("--out", required=True)
        a = ap.parse_args()
        apply(a.excess, a.out)
