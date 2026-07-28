# Updated MATSim — Baltimore traffic assignment, calibration & validation

Fourth stage of the VAE → SILO → MITO → **MATSim** pipeline. Takes the calibrated MITO travel demand
(per-purpose Apollo mode choice, validated to RTS) and runs a MATSim traffic assignment for the
**Baltimore study area (6-county BMR)**, with mapped public transport, then validates and calibrates the
assigned link volumes against **2017 MDOT SHA AADT count stations**.

## Study area & base year
- **Area:** 6-county Baltimore Metropolitan Region — Baltimore City + Baltimore, Anne Arundel, Howard, Harford, Carroll counties.
- **Base year:** 2017 (the RTS survey year the MITO mode choice was calibrated to). MITO plan/skim year currently 2019; demand is cross-sectional — a 2017 population/skim swap is a follow-up.

## Pipeline
```
GTFS (MTA MD) ──┐
                ├─ pt2matsim ─► PT-mapped multimodal network + transit schedule + vehicles
OSM (BMR road) ─┘
                                          │
MITO demand (calibrated mode choice) ─► MATSim plans (10% intraflow subsample, flowCapFactor 0.1)
                                          │
                                   MATSim Controler (car mobsim + PT) ─► assigned link volumes
                                          │
2017 AADT stations (MDOT SHA) ─► GIS validation (GEH / %RMSE per station) ─► Cadyts calibration ─► re-validate
```

## Folder layout
- `data/` — **all raw downloaded data** (one folder):
  - `mta_{local-bus,light-rail,metro,marc,commuter-bus}.zip` — current MTA Maryland GTFS (5 services).
  - `aadt_2017_bmr.geojson` — 3,787 MDOT SHA AADT stations in the BMR with `AADT_2017`, `AAWDT_2017`
    (weekday), `K_FACTOR` (peak-hour %), `D_FACTOR` (directional), vehicle-class splits, point geometry.
  - `tmas_2017/` — **FHWA TMAS 2017 hourly continuous-count data** (all 12 months, MD `.VOL` files in
    `md_vol/`) + `Station_Data_Extract..._2017.txt` (lat/lon, county, route). 35 unique BMR continuous
    stations with true 24-h weekday profiles (validated parse: realistic AM/PM peaks). `bmr_tmas_stations.json`.
  - `maryland-latest.osm.pbf` — OSM road extract (Geofabrik) for building the network.
- `input/` — **processed MATSim inputs**: `network/` (PT-mapped network.xml), `config/`, `population/` (plans), schedule/vehicles.
- `tools/` — pt2matsim jar, osmosis, helper binaries.
- `runs/` — MATSim output scenarios (one subdir per run).
- `validation/` — `figures/`, `gis/` (count-vs-volume overlays, GEH maps), scorecards.
- `code/` — build/run/validation/calibration scripts.
- `docs/` — this README + the living report/deck.
- `scratch/` — temporary working files.

## Engine
MATSim is embedded in MITO (`de.tum.bgu.msm.trafficAssignment`): setting `run.traffic.assignment=true`
in the MITO properties makes `MitoMuc` build the population and run a MATSim `Controler` after the demand
models. `ConfigureMatsim` sets `flowCapFactor = SILO_SAMPLING_RATE(1.0) × tripScaling(0.1) = 0.1` to match
the 10% intraflow subsample, threads=16, network/schedule/vehicles from the MITO properties.
Build JDK: `temurin-21-x64`. Run via the MITO run script (or a dedicated MATSim runner in `code/`).

## Data sources
- **GTFS** — MTA Maryland feeds: `https://feeds.mta.maryland.gov/gtfs/{local-bus,light-rail,metro,marc,commuter-bus}`.
  Current feeds (post-BaltimoreLink, the June-2017 bus overhaul — a reasonable 2017-H2 proxy). A 2017 archived
  snapshot (Transitland / Mobility Database) is a refinement.
- **AADT** — MDOT SHA Traffic Monitoring System. AGOL feature service
  `services.arcgis.com/njFNhDsUCentVYJW/.../MDOT_SHA_Annual_Average_Daily_Traffic/FeatureServer/0` (points),
  fields incl. `AADT_2017`, `AAWDT_2017`, `K_FACTOR`, `D_FACTOR`. A "AADT 2017 (File Geodatabase)" item also exists.
  Daily + peak-hour (K) supports peak-hour validation; full 24-h hourly needs the 84 continuous ATR stations
  (TMS Data Extractor) — pursued as a refinement.

## Status (update this!)
- [x] Folder structure + plan.
- [x] GTFS collected (5 MTA MD services) → `data/`.
- [x] AADT 2017 BMR stations (3,787) → `data/aadt_2017_bmr.geojson`.
- [x] FHWA TMAS 2017 hourly counts (12 months, 35 BMR continuous stations) → `data/tmas_2017/`.
- [x] OSM Maryland road extract → `data/maryland-latest.osm.pbf`.
- [x] pt2matsim built (v24.4, MATSim-2024 / Java-21) → `tools/`.
- [x] MATSim road network (220,651 nodes / 487,144 links, EPSG:26985) → `input/network/bmr_network.xml.gz`.
- [x] GTFS merged (5 feeds) → unmapped schedule (107 lines / 1,477 routes / 4,678 stops) → `input/pt/`.
- [x] **pt2matsim PT mapping** → `input/network/bmr_network_pt.xml.gz` + `input/pt/schedule_mapped.xml.gz`
      (+ `transitVehicles.xml.gz`); all 1,477 routes mapped, 5,086 stops; map: `validation/figures/pt_network_checkpoint.png`.
- [ ] MATSim config + run with calibrated MITO demand.
- [ ] GIS validation vs AADT (GEH/%RMSE per station).
- [ ] Cadyts calibration to counts + re-validation.

## Validation method — GIS-based (`code/validate_matsim_counts.py`)
Each AADT station (point) is snapped to the best nearby MATSim **car** link (highest road hierarchy within
45 m, then nearest), with the opposing-direction link paired so both directions sum to the bidirectional
AADT. 3,200 of 3,787 stations match (84.5%; the rest sit on residential/local roads we deliberately dropped).
After a run, MATSim events → per-link hourly volumes × (1/sample) → compared to `AADT_2017` (daily) and the
35 TMAS continuous stations (24-h profiles). Metrics: **GEH** (target GEH<5 for >85% of links), %RMSE, bias.

**GIS deliverables** (`validation/gis/`, `validation/figures/`):
- `baltimore_validation.gpkg` — **QGIS/ArcGIS GeoPackage** with `aadt_stations` (obs/model/GEH/%diff) +
  `matched_links` (modelled volume) layers.
- `validation_map.html` — **interactive folium map** on an OSM basemap; stations coloured by GEH (green<5 /
  amber<10 / red), click for obs-vs-model.
- `gis_geh_bias.png` — static **GEH choropleth** + **spatial-bias** (over/under-prediction) maps on the network.
- `aadt_link_match.png`, `aadt_scatter.png` — match-quality + obs-vs-model scatter.
Stages: `match` (snap, done) · `validate <events> <scale>` (volumes+GEH) · `gis` (layers+maps).
