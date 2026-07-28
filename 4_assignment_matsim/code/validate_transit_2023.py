#!/usr/bin/env python3
"""
Task 4 - Deliverable B: extract SIMULATED transit boardings from MATSim events.

10% resident sample (flowCapacityFactor 0.10) -> all counts scaled x10.

Mode-mapping method
-------------------
Each MATSim transitLine id is IDENTICAL to a GTFS route_id (verified: 107 lines
== 107 GTFS routes, 1:1). GTFS route ids carry an agency-mode prefix, and the
GTFS route_type confirms it:
    prefix  route_type  ->  NTD mode
    bus:    3 (Bus)         Local Bus            (motorbus)
    cb:     3 (Bus)         Commuter Bus         (motorbus, MB)
    lr:     0 (Tram/LR)     Light Rail           (LR)
    mt:     1 (Subway)      Metro Subway         (Heavy Rail, HR)
    marc:   2 (Rail)        Commuter Rail (MARC) (CR)
So mode is assigned by looking each transitLine id up in GTFS routes.txt
(prefix + route_type). The MATSim transit vehicleType (Bus/Rail/Subway/Tram)
agrees but cannot split Local Bus vs Commuter Bus (both use "Bus" vehicles),
so the GTFS/line-id mapping is authoritative.

Boarding count method
---------------------
Boardings = PersonEntersVehicle events on a transit vehicle, EXCLUDING the
transit driver. Drivers are the "pt_..." agents (verified: every
TransitDriverStarts driverId begins "pt_veh_"). Events are time-ordered, so we
stream them: each TransitDriverStarts tells us the (line, route) a vehicle is
currently serving; every following non-driver PersonEntersVehicle on that
vehicle is a boarding attributed to that line/route -> mode. This cleanly
handles vehicle reuse across routes and splits Local vs Commuter bus.
"""
import gzip, re, csv, os, sys
from collections import defaultdict

BASE = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
# Which MATSim run to read (defaults to the base output/; override for the transit-fix re-run):
#   NETVAL_OUTDIR=scenarios/01_base_no_pricing/output_transitfix NETVAL_SUB=transitfix python validate_transit_2023.py
_OUT = os.environ.get("NETVAL_OUTDIR", "scenarios/01_base_no_pricing/output")
_SUB = os.environ.get("NETVAL_SUB", "")
OUT_DIR = os.path.join(BASE, _OUT)
GTFS = os.path.join(BASE, "data/gtfs_mta_merged")
RES_DIR = os.path.join(BASE, "network_validation_2023" if not _SUB else f"network_validation_2023/{_SUB}", "transit")
os.makedirs(RES_DIR, exist_ok=True)
SCALE = 10  # 10% sample

VEH_XML = os.path.join(OUT_DIR, "output_transitVehicles.xml.gz")
SCHED_XML = os.path.join(OUT_DIR, "output_transitSchedule.xml.gz")
EVENTS_XML = os.path.join(OUT_DIR, "output_events.xml.gz")

# ---- mode mapping from GTFS routes.txt -----------------------------------
PREFIX_MODE = {
    "bus": "Local Bus",
    "cb": "Commuter Bus",
    "lr": "Light Rail",
    "mt": "Metro Subway",
    "marc": "Commuter Rail (MARC)",
}
ROUTE_TYPE_NAME = {"0": "Tram/LightRail", "1": "Subway/Metro", "2": "Rail", "3": "Bus"}

def load_gtfs_routes():
    """route_id -> (mode, route_type, short, long)."""
    routes = {}
    with open(os.path.join(GTFS, "routes.txt"), newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rid = row["route_id"]
            prefix = rid.split(":")[0]
            mode = PREFIX_MODE.get(prefix, "UNKNOWN:" + prefix)
            routes[rid] = (mode, row.get("route_type", ""),
                           row.get("route_short_name", ""),
                           row.get("route_long_name", ""))
    return routes

# ---- 1) transit vehicle ids + type ---------------------------------------
def load_transit_vehicles():
    veh_type = {}
    vre = re.compile(r'<vehicle id="([^"]+)" type="([^"]+)"')
    with gzip.open(VEH_XML, "rt") as f:
        for line in f:
            m = vre.search(line)
            if m:
                veh_type[m.group(1)] = m.group(2)
    return veh_type

# ---- 2) schedule: line -> mode, and departures (documentation/validation)-
def load_schedule(gtfs_routes):
    """Return line_ids set and line->mode. Also count departures per line."""
    line_mode = {}
    dep_count = defaultdict(int)
    cur_line = None
    line_re = re.compile(r'<transitLine id="([^"]+)"')
    dep_re = re.compile(r'<departure ')
    with gzip.open(SCHED_XML, "rt") as f:
        for line in f:
            m = line_re.search(line)
            if m:
                cur_line = m.group(1)
                mode = gtfs_routes.get(cur_line, (None,))[0]
                if mode is None:
                    # fallback: prefix
                    mode = PREFIX_MODE.get(cur_line.split(":")[0], "UNKNOWN")
                line_mode[cur_line] = mode
            elif dep_re.search(line) and cur_line:
                dep_count[cur_line] += 1
    return line_mode, dep_count

# ---- 3) stream events -----------------------------------------------------
def stream_events(transit_vehs, line_mode):
    """Attribute non-driver PersonEntersVehicle to current route via
    TransitDriverStarts tracking. Returns boardings_by_line, boardings_by_mode."""
    veh_cur_line = {}   # vehicle -> current transitLineId
    veh_cur_route = {}  # vehicle -> current transitRouteId
    board_line = defaultdict(int)
    board_route = defaultdict(int)   # (line,route) -> count
    board_mode = defaultdict(int)
    driver_enters = 0
    non_transit_enters = 0
    total_transit_boardings = 0

    tds_re = re.compile(
        r'type="TransitDriverStarts" driverId="([^"]*)" vehicleId="([^"]*)" '
        r'transitLineId="([^"]*)" transitRouteId="([^"]*)"')
    pev_re = re.compile(
        r'type="PersonEntersVehicle" person="([^"]*)" vehicle="([^"]*)"')

    n = 0
    with gzip.open(EVENTS_XML, "rt") as f:
        for raw in f:
            # cheap pre-filter
            if 'PersonEntersVehicle' in raw:
                m = pev_re.search(raw)
                if not m:
                    continue
                person, veh = m.group(1), m.group(2)
                if veh not in transit_vehs:
                    non_transit_enters += 1
                    continue
                if person.startswith("pt_"):
                    driver_enters += 1
                    continue
                # a passenger boarding on a transit vehicle
                line = veh_cur_line.get(veh)
                route = veh_cur_route.get(veh)
                if line is None:
                    # boarding before any TransitDriverStarts (shouldn't happen
                    # since driver starts first); fall back to vehicle suffix
                    line = "UNASSIGNED"
                    mode = "UNKNOWN"
                else:
                    mode = line_mode.get(line, PREFIX_MODE.get(line.split(":")[0], "UNKNOWN"))
                board_line[line] += 1
                board_route[(line, route)] += 1
                board_mode[mode] += 1
                total_transit_boardings += 1
            elif 'TransitDriverStarts' in raw:
                m = tds_re.search(raw)
                if m:
                    _, veh, line, route = m.groups()
                    veh_cur_line[veh] = line
                    veh_cur_route[veh] = route
            n += 1
            if n % 20_000_000 == 0:
                sys.stderr.write(f"  ...{n:,} event lines, "
                                 f"{total_transit_boardings:,} boardings so far\n")
    stats = dict(driver_enters=driver_enters,
                 non_transit_enters=non_transit_enters,
                 total_transit_boardings=total_transit_boardings)
    return board_line, board_route, board_mode, stats

# ---- 4) sim-vs-NTD comparison table --------------------------------------
# NTD 2023 MTA-Maryland avg-weekday boardings (fixed-route) — the OBSERVED target the
# ABIT transit ASCs were re-anchored to. Written as transit_validation_2023.csv so the
# figure scripts (make_nyc_style_figures / make_transitfix_figures) have their input.
NTD_OBS = os.path.join(BASE, "data/transit_ridership_2023/observed_ridership_2023.csv")
# sim board_mode label -> NTD observed-file mode label
SIM_TO_NTD = {
    "Local Bus":            "Bus (Local Bus, motorbus)",
    "Commuter Bus":         "Commuter Bus",
    "Light Rail":           "Light Rail",
    "Metro Subway":         "Heavy Rail (Metro Subway)",
    "Commuter Rail (MARC)": "Commuter Rail (MARC)",
}

def write_ntd_comparison(board_mode):
    """Join sim boardings (x10) to NTD observed weekday boardings; write transit_validation_2023.csv.
    Demand Response (paratransit) is excluded (no fixed route simulated in MATSim)."""
    obs = {}
    with open(NTD_OBS, newline="") as f:
        for row in csv.DictReader(f):
            obs[row["mode"]] = float(row["avg_weekday_boardings"])
    out = os.path.join(RES_DIR, "transit_validation_2023.csv")
    sim_tot = 0.0; obs_tot = 0.0; diffs = []
    rows = []
    for sim_mode, ntd_mode in SIM_TO_NTD.items():
        o = obs.get(ntd_mode, float("nan"))
        s = board_mode.get(sim_mode, 0) * SCALE
        dp = (s - o) / o * 100 if o else float("nan")
        rows.append([ntd_mode, int(o), int(s), round(dp, 1)])
        sim_tot += s; obs_tot += o
        if o: diffs.append(abs(dp))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "observed_weekday", "sim_daily_x10", "diff_pct"])
        w.writerows(rows)
        w.writerow(["TOTAL (excl. Demand Response)", int(obs_tot), int(sim_tot),
                    round((sim_tot - obs_tot) / obs_tot * 100, 1)])
        w.writerow(["AVG ABS % DIFF (NYC Table-5 metric)", "", "",
                    round(sum(diffs) / len(diffs), 1) if diffs else ""])
    print(f"\n=== SIM vs NTD (x10) ===  total {sim_tot:,.0f} vs {obs_tot:,.0f} "
          f"({(sim_tot-obs_tot)/obs_tot*100:+.1f}%)")
    print(f"  wrote {out}")
    return out

def main():
    sys.stderr.write("Loading GTFS routes...\n")
    gtfs_routes = load_gtfs_routes()
    sys.stderr.write("Loading transit vehicles...\n")
    veh_type = load_transit_vehicles()
    transit_vehs = set(veh_type)
    sys.stderr.write(f"  {len(transit_vehs):,} transit vehicles\n")
    sys.stderr.write("Loading schedule...\n")
    line_mode, dep_count = load_schedule(gtfs_routes)
    sys.stderr.write(f"  {len(line_mode)} transit lines\n")
    sys.stderr.write("Streaming events (this takes a few minutes)...\n")
    board_line, board_route, board_mode, stats = stream_events(transit_vehs, line_mode)

    # ---- write by-mode -----------------------------------------------------
    mode_csv = os.path.join(RES_DIR, "sim_boardings_by_mode.csv")
    with open(mode_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "sim_boardings_sample", "sim_boardings_x10"])
        for mode in sorted(board_mode, key=lambda m: -board_mode[m]):
            w.writerow([mode, board_mode[mode], board_mode[mode] * SCALE])
        total = sum(board_mode.values())
        w.writerow(["TOTAL", total, total * SCALE])

    # ---- write by-route/line ----------------------------------------------
    route_csv = os.path.join(RES_DIR, "sim_boardings_by_route.csv")
    with open(route_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["transit_line", "mode", "route_short_name", "route_long_name",
                    "n_departures", "sim_boardings_sample", "sim_boardings_x10"])
        for line in sorted(board_line, key=lambda l: -board_line[l]):
            mode = line_mode.get(line, "UNKNOWN")
            meta = gtfs_routes.get(line, (None, "", "", ""))
            w.writerow([line, mode, meta[2], meta[3], dep_count.get(line, ""),
                        board_line[line], board_line[line] * SCALE])

    # ---- console summary ---------------------------------------------------
    print("\n=== SIM boardings by mode (x10) ===")
    for mode in sorted(board_mode, key=lambda m: -board_mode[m]):
        print(f"  {mode:24s} {board_mode[mode]*SCALE:>10,}")
    print(f"  {'TOTAL':24s} {sum(board_mode.values())*SCALE:>10,}")
    print("\n=== diagnostics ===")
    print(f"  driver PersonEntersVehicle excluded : {stats['driver_enters']:,}")
    print(f"  non-transit PersonEntersVehicle     : {stats['non_transit_enters']:,}")
    print(f"  transit passenger boardings (sample): {stats['total_transit_boardings']:,}")
    # ---- sim vs NTD comparison (input for figure 7 / fig_c) ----------------
    ntd_csv = write_ntd_comparison(board_mode)
    print(f"\nWrote:\n  {mode_csv}\n  {route_csv}\n  {ntd_csv}")

if __name__ == "__main__":
    main()
