#!/usr/bin/env python3
"""ASC re-anchor for the I-695 no-toll base (MODE_SCORER_MAPPING.md Sec. 4).

Reads a MATSim modestats.csv (last iteration = relaxed shares), compares to the validated ABIT demand
target shares, and prints the updated per-mode ASCs:  ASC_m <- ASC_m + ln(target_m / sim_m)  (car frozen).

Usage: reanchor_asc.py <modestats.csv> <ascCar> <ascPt> <ascRide> <ascWalk> <ascBike>
"""
import sys, math, os

AMP = float(os.environ.get("AMP", "2.0"))        # amplify ln step for ride/walk/bike to converge faster
CLAMP = float(os.environ.get("CLAMP", "3.0"))    # max single-pass ASC change
FREEZE_PP = float(os.environ.get("FREEZE_PP", "1.0"))  # freeze a mode's ASC once within this gap (anti-oscillation)
# Modes to hold fixed (comma list, e.g. "pt,walk,bike"): they sit at their structural short-trip floors,
# so re-anchoring them just reshuffles the equilibrium. Only the non-floored mode (ride) is re-anchored.
FREEZE_MODES = set(m.strip() for m in os.environ.get("FREEZE_MODES", "").split(",") if m.strip())

# Validated-base target shares (coordinator, main-mode trips): car .762 / ride .179 / walk .028 / bike .008 / pt .021
TARGET = {"car": 0.762, "pt": 0.021, "ride": 0.179, "walk": 0.028, "bike": 0.008}
# Override with the CURRENT demand's shares via env, e.g. TARGETS="car=0.776,ride=0.1627,walk=0.0366,pt=0.018,bike=0.0068"
if os.environ.get("TARGETS"):
    TARGET = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in os.environ["TARGETS"].split(",")}
    s = sum(TARGET.values()); TARGET = {m: v/s for m, v in TARGET.items()}

def main():
    ms = sys.argv[1]
    asc = {"car": float(sys.argv[2]), "pt": float(sys.argv[3]), "ride": float(sys.argv[4]),
           "walk": float(sys.argv[5]), "bike": float(sys.argv[6])}
    with open(ms) as f:
        header = f.readline().strip().split(";")
        last = None
        for line in f:
            if line.strip():
                last = line.strip().split(";")
    cols = {h: i for i, h in enumerate(header)}
    # a mode absent from modestats = 0 share (e.g. pt fully absorbed to walk fallback at iter 0)
    sim = {m: (float(last[cols[m]]) if m in cols else 0.0) for m in ("bike", "car", "pt", "ride", "walk")}
    tot = sum(sim.values())
    sim = {m: v / tot for m, v in sim.items()}  # renormalize defensively

    print(f"# modestats last iter (iter={last[0]}):")
    new_asc = dict(asc)
    worst = 0.0
    gaps = {}
    for m in ("car", "ride", "walk", "pt", "bike"):
        gap_pp = (sim[m] - TARGET[m]) * 100
        gaps[m] = gap_pp
        worst = max(worst, abs(gap_pp))
        # REFERENCE-CORRECTED MNL re-anchor (2026-07-12): with car frozen as the reference, the exact
        # one-shot logit update for every other mode is
        #     step_m = ln(target_m/sim_m) - ln(target_car/sim_car)
        # The old formula omitted the second term, so each pass under-shot by the full car deficit
        # (~1.0 utils/pass) -> crawling convergence. Freeze test is on the RATIO (vs car), not pp.
        car_corr = math.log(TARGET["car"] / max(sim["car"], 1e-4))
        ratio_gap = math.log(TARGET[m] / max(sim[m], 1e-4)) - car_corr
        if m == "car":
            note = "(reference, frozen)"
        elif m in FREEZE_MODES:
            note = f"ASC held {asc[m]:+.4f} (frozen at floor by request)"
        elif abs(ratio_gap) < 0.10 and abs(gap_pp) < FREEZE_PP:
            note = f"ASC held {asc[m]:+.4f} (ratio gap {ratio_gap:+.3f} < 0.10 -> converged)"
        else:
            step = AMP * ratio_gap
            step = max(-CLAMP, min(CLAMP, step))
            new_asc[m] = asc[m] + step
            note = f"ASC {asc[m]:+.4f} -> {new_asc[m]:+.4f} (step {step:+.3f}, ref-corrected)"
        print(f"#   {m:5s} sim={sim[m]*100:6.2f}%  target={TARGET[m]*100:6.2f}%  gap={gap_pp:+6.2f}pp  {note}")
    print(f"# worst gap = {worst:.2f} pp")
    print(f"WORST_GAP_PP={worst:.3f}")
    print(f"CAR_GAP_PP={abs(gaps['car']):.3f}")
    print(f"RIDE_GAP_PP={abs(gaps['ride']):.3f}")
    print(f"NEW_ASC car={new_asc['car']:.4f} pt={new_asc['pt']:.4f} ride={new_asc['ride']:.4f} "
          f"walk={new_asc['walk']:.4f} bike={new_asc['bike']:.4f}")
    # bare numeric line (car pt ride walk bike) for easy shell parsing
    print(f"ASC_VALUES {new_asc['car']:.4f} {new_asc['pt']:.4f} {new_asc['ride']:.4f} "
          f"{new_asc['walk']:.4f} {new_asc['bike']:.4f}")

if __name__ == "__main__":
    main()
