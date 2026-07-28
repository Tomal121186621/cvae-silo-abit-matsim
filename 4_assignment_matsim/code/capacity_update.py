#!/usr/bin/env python3
"""Component 3 -- SPSA-lite per-facility capacity update.

Usage:  capacity_update.py <calibration_gate.json> <caps_in.json> <caps_out.json>

For each calibratable facility f, rho_f = median(sim/obs) over the CALIBRATION stations of
that facility (read from the gate json's per_facility.<...>.median_ratio). If the model
over-assigns (rho>1) we lower capacity, if it under-assigns (rho<1) we raise it:

    cap_f  <-  cap_f * (1/rho_f)**0.5           (sqrt damping -> gentle steps)

then Delta clamped to +/-25% per pass, then clamped to the per-facility factor band:
    freeway  FIXED at 1.0 (2000/lane -- not calibrated)
    ramp     FIXED (no calibration stations)
    principal [0.47, 0.80]   (base 1500/lane -> 705..1200)
    minor     [0.80, 1.00]   (base 1000/lane -> 800..1000)
    collector [0.83, 1.17]   (base  600/lane -> 498..702)
"""
import json, sys

# station facility name -> caps.json facility key
STN2CAP = {"Principal Arterial": "principal", "Minor Arterial": "minor",
           "Collector/Local": "collector"}
# per-facility factor bounds; freeway/ramp fixed (None => don't update)
BOUNDS = {"principal": (0.47, 0.80), "minor": (0.80, 1.00), "collector": (0.83, 1.17)}
MAX_STEP = 0.25   # <= +/-25% change per pass


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: capacity_update.py <gate.json> <caps_in.json> <caps_out.json>")
    gate = json.load(open(sys.argv[1]))
    caps = json.load(open(sys.argv[2]))
    per = gate.get("per_facility", {})

    # rho per caps-facility from the calibration median ratios
    rho = {}
    for stn_fac, cap_fac in STN2CAP.items():
        m = per.get(stn_fac)
        if m and m.get("median_ratio") is not None and m["median_ratio"] == m["median_ratio"]:
            rho[cap_fac] = float(m["median_ratio"])

    new = dict(caps)
    for fac, (lo, hi) in BOUNDS.items():
        if fac not in caps:
            continue
        r = rho.get(fac)
        if r is None or r <= 0:
            print(f"  {fac:<10} rho=n/a       cap {caps[fac]:.3f} -> {caps[fac]:.3f} (held; no stations)")
            continue
        raw = caps[fac] * (1.0/r) ** 0.5
        step_lo = caps[fac] * (1 - MAX_STEP); step_hi = caps[fac] * (1 + MAX_STEP)
        capped = min(max(raw, step_lo), step_hi)
        clamped = min(max(capped, lo), hi)
        new[fac] = round(clamped, 4)
        print(f"  {fac:<10} rho={r:.3f}  cap {caps[fac]:.3f} -> {new[fac]:.3f} "
              f"(raw {raw:.3f}, step-clamp {capped:.3f}, band[{lo},{hi}])")

    json.dump(new, open(sys.argv[3], "w"), indent=2)
    print("wrote", sys.argv[3], json.dumps(new))


if __name__ == "__main__":
    main()
