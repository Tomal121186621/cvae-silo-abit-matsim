# GPS-derived I-95 trajectories vs the ABIT/SILO model

Side-by-side time–space comparison of the **I-95 corridor** (Washington DC ↔ Delaware line):
**(A)** trips from a GPS/MDLD device dataset, routed through our MATSim network, vs
**(B)** our ABIT/SILO base-2023 model. This is a **trajectory VISUAL comparison**, not a
calibrated volume study.

## What this run is
- **GPS source:** `../../../input/WMA_device_TripRosters_20220504.csv` — WMA/DC-centric device
  trip rosters, **O–D endpoints only (no waypoints)**: origin `lat/lon/utc_timestamp_1`, dest
  `lat/lon/utc_timestamp_2`, `linked_trip_mode` (0 = car-dominant, kept). ~416k trips total.
- **Network (EPSG:26985):** `../output_base/base_hybrid/output_network.xml.gz` (referenced, not
  copied). NOTE: a corrected `base_speedfix` network was still running when this was built and is
  **not** used here.
- **Model I-95 events:** `../via_i95/i95_events.xml.gz` (the base_hybrid run filtered to I-95
  entered/left-link events). Corridor link ids + geometry: `../via_i95/i95_link_ids.txt` (288 links).
- **Milepost method:** projection of each I-95 link midpoint onto the corridor SW→NE axis
  (0 mi = DC end, ~54 mi = Delaware line), reusing the axis approach from
  `network_validation_2023/FINAL_FIGURES/i95_context_map/build_i95_data.py`.

## Pipeline (scripts in this folder, run in order)
1. `01_build_net_and_select.py` — parse the MATSim network into a car graph; build the I-95
   milepost map; keep GPS **mode 0** trips whose **straight O→D line crosses the I-95 corridor
   3 km buffer** (pre-filter for trips that would traverse the corridor). → `cache/`.
2. `02_route_gps.py` — route every candidate O→D on the car network via **free-flow shortest
   path** (scipy dijkstra; nodes snapped with a KD-tree). A trip "uses I-95" if its route covers
   **≥ 1 mi over ≥ 2 I-95 links**. Emits per-trip (time, milepost, speed) points along I-95.
3. `03_write_matsim_plans.py` — write the GPS-derived **MATSim population** `input/gps_i95_plans.xml.gz`
   (one person per I-95 trip: home act @ O, car leg, work act @ D, departure = local
   `utc_timestamp_1 + utc_offset_1`) + `input/config_gps_sim.xml` (single-mobsim-pass config; can
   be fed to a full MATSim run — outputs would land in `output/matsim_run/`).
4. `04_figure.py` — parse the model events into I-95 trajectories and draw the two-panel figure.

## Counts (this run)
- Mode-0 (car) GPS trips: **352,442**
- GPS candidates (straight line crosses I-95 3 km buffer): **9,746**
- GPS trips actually **routed onto I-95** (≥1 mi corridor): **3,193**
- Model resident vehicles on I-95 (from events): **23,084**

## Folders
- `input/` — GPS-derived MATSim plans (`gps_i95_plans.xml.gz`) + `config_gps_sim.xml`. Network is
  referenced from `../output_base/base_hybrid/` (not duplicated).
- `output/` — routing outputs: `gps_i95_traj.parquet` (the routed I-95 (time,milepost,speed)
  points — this is the "assignment" output of the shortest-path router), `gps_candidates.parquet`,
  `select_stats.json`, `route_log.txt`. (If you run the MATSim config, its events/linkstats land in
  `output/matsim_run/`.)
- `figures/` — `i95_gps_vs_model_timespace.png` (also copied to
  `network_validation_2023/FINAL_FIGURES/i95_gps_vs_model/`).

## Honest caveats (state on the slide)
- **GPS is O–D-only:** the I-95 route and the times along it are **inferred by routing**, not
  observed — no in-vehicle waypoints exist. Free-flow shortest path means the GPS-panel speeds are
  essentially link free-flow (no observed congestion is recoverable from O–D + total time).
- **GPS is a device SAMPLE**, not expanded to population, and coverage is **WMA/DC-centric** — so
  northern-MD I-95 volumes thin out and there is a coverage gap mid-corridor.
- **Our model is resident-only:** I-95 through / long-distance external traffic is not modeled, so
  the corridor is under-loaded and runs near free-flow. The comparison shows congestion **timing
  and location**, not validated absolute volumes or speeds.
