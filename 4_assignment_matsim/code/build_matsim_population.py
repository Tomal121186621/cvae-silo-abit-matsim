#!/usr/bin/env python3
"""Build a MATSim population (plans) from the calibrated MITO BMR sub-area trips.

Each MITO trip becomes one agent with a 2-activity plan (origin act -> leg -> destination act),
using the trip's ORIGIN/DESTINATION COORDINATES (EPSG:26985, the network CRS) and the MITO-chosen
mode. Activities are coordinate-only (no link refs) so MATSim assigns links on the new pt2matsim
network and routes from scratch. This decouples the assignment from MITO's old MATSim-11 network.

Mode mapping (for AADT car-volume validation):
  autoDriver -> car   (loads the road network = the AADT vehicle)
  autoPassenger, sr -> ride  (teleported; passengers add no extra vehicle)
  bus, train, tramMetro -> pt
  walk -> walk ;  bicycle -> bike   (teleported)

The 3 sub-sample flows (intra/in/out) are all 10% samples -> MATSim flowCapFactor 0.1; multiply link
volumes by 10 to compare with full AADT.
"""
import csv, gzip, sys
from pathlib import Path

# optional further sub-sampling of the (already 10%) MITO sample: pass a fraction, e.g. 0.1 -> keep every
# 10th trip = 1% overall sample (MATSim flowCapFactor = 0.1 * fraction). Default 1.0 (full 10% sample).
SAMPLE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
STEP = max(1, round(1.0 / SAMPLE))
SUFFIX = "" if STEP == 1 else f"_p{int(round(10*SAMPLE)):02d}"   # _p01 = 1% overall

MITO = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MITO/code/MITO_Inputs/scenOutput/BMR_subsample_trips/2019/microData")
OUT = Path(f"/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/input/population/bmr_plans{SUFFIX}.xml.gz")
FLOWS = ["subsampledIntraflowTrips.csv","subsampledOutflowTrips.csv","subsampledInflowTrips.csv"]
MODE = {"autoDriver":"car","autoPassenger":"ride","sr":"ride","bus":"pt","train":"pt",
        "tramMetro":"pt","walk":"walk","bicycle":"bike"}
# destination activity type by MITO purpose; origin = "home" for home-based, else "other"
DEST = {"HBW":"work","HBE":"education","HBS":"shopping","HBO":"other","NHBW":"work","NHBO":"other"}
HOMEBASED = {"HBW","HBE","HBS","HBO"}

def esc(s): return str(s).replace("&","&amp;").replace('"',"&quot;").replace("<","&lt;")

def main():
    n=0; bymode={}; legs=[0]
    with gzip.open(OUT,"wt") as w:
        w.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        w.write('<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n')
        w.write('<population>\n')
        seen=0
        for fn in FLOWS:
            fp=MITO/fn
            with open(fp) as f:
                for r in csv.DictReader(f):
                    seen+=1
                    if (seen % STEP) != 0:   # sub-sample: keep every STEP-th trip
                        continue
                    try:
                        ox,oy=float(r["originX"]),float(r["originY"])
                        dx,dy=float(r["destinationX"]),float(r["destinationY"])
                        dep=int(float(r["departure_time"]))*60   # minutes -> seconds
                    except (ValueError,KeyError):
                        continue
                    mode=MODE.get(r["mode"],"car"); purp=r.get("purpose","HBO")
                    oact="home" if purp in HOMEBASED else "other"
                    dact=DEST.get(purp,"other")
                    pid=f'{r["person"]}_{n}'
                    dep=max(1,min(dep,30*3600-1))
                    # MITO home-based rows are TOURS (one outbound + one return departure on the same row;
                    # the MITO time-of-day validation expands both -> two clear peaks). So emit the return leg
                    # (dest->origin at the return time, SAME mode). This doubles home-based legs, so the run
                    # uses flowCapFactor ~0.10 (2x the one-leg value) to keep the network balance + match AADT.
                    dep_ret=None
                    if purp in HOMEBASED:
                        rt=r.get("departure_time_return","")
                        if rt not in ("","-1",None):
                            try:
                                v=int(float(rt))*60
                                if dep < v < 30*3600: dep_ret=v
                            except ValueError: pass
                    w.write(f'<person id="{esc(pid)}">\n<plan selected="yes">\n')
                    w.write(f'<activity type="{oact}" x="{ox:.2f}" y="{oy:.2f}" end_time="{dep}"/>\n')
                    w.write(f'<leg mode="{mode}"/>\n')
                    if dep_ret:
                        w.write(f'<activity type="{dact}" x="{dx:.2f}" y="{dy:.2f}" end_time="{dep_ret}"/>\n')
                        w.write(f'<leg mode="{mode}"/>\n')
                        w.write(f'<activity type="{oact}" x="{ox:.2f}" y="{oy:.2f}"/>\n')
                        bymode[mode]=bymode.get(mode,0)+2; legs[0]+=2
                    else:
                        w.write(f'<activity type="{dact}" x="{dx:.2f}" y="{dy:.2f}"/>\n')
                        bymode[mode]=bymode.get(mode,0)+1; legs[0]+=1
                    w.write('</plan>\n</person>\n')
                    n+=1
            print(f"  {fn}: cumulative agents={n:,}")
        w.write('</population>\n')
    print(f"wrote {OUT}  ({n:,} agents, {legs[0]:,} legs incl. returns)")
    print("by mode (legs):", bymode)
    tot=sum(bymode.values())
    print("mode share (legs %):", {m:round(100*c/tot,2) for m,c in sorted(bymode.items())})

if __name__=="__main__":
    main()
