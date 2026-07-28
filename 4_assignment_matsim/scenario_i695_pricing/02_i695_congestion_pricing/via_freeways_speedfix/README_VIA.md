# Visualizing the MAJOR FREEWAY NETWORK in Via (Simunto) — corrected base run

This folder is a **freeway-only** package extracted from the **corrected** MATSim base run
(`output_base/base_speedfix/`). Unlike the single-corridor `../via_i95_speedfix/` package, this one
contains **the whole interstate/freeway system** — every `motorway`-class mainline **plus all
interchange ramps** — so you can watch vehicles move **between** freeways (merge, weave, transfer at
interchanges), not just along one corridor.

> **Corrected-network build.** Freeway freespeeds were fixed to a realistic **~29 m/s (65 mph)** on
> the mainlines (the earlier broken network capped them at ~21 m/s / 47 mph). Use THIS package.

## What's in the subnetwork

**9,845 links / 9,344 nodes.** Selection rule (robust, facility-class based):
- every link of OSM class **`motorway`** (the network audit's "Interstate/Freeway" class — high
  freespeed + high capacity), **UNION** the authoritative I-95 (`../via_i95/i95_link_ids.txt`, 597)
  and I-695 (`../toll_research/i695_link_ids.txt`, 604) link sets, **PLUS**
- all **`motorway_link`** interchange ramps that connect (iteratively) to a freeway node — so ramps
  form complete interchange structures and the freeways are one connected system.
- local/arterial roads are **excluded**.

### Interstates present (spot-checked by location — see the QA map)

| `freeway_tag` | links | what it is |
|---------------|-------|-----------|
| `I-95`  | 597 | John F. Kennedy Mem. Hwy corridor, NE (Delaware) ↔ SW (DC), thru Fort McHenry Tunnel |
| `I-695` | 604 | Baltimore Beltway (full ring) |
| `I-83`  | 336 | Jones Falls Expwy + Baltimore–Harrisburg Expwy (north out of Baltimore) |
| `I-895` | 286 | Harbor Tunnel Thruway (parallel to I-95 thru the harbor) |
| `I-70`  | 253 | Korean War Veterans Mem. Hwy (E–W, west of Baltimore, ends at I-695) |
| `other_freeway` | 3,205 | remaining motorway mainlines: Capital Beltway (I-495), BW Pkwy, ICC (MD-200), John Hanson Hwy (US-50), etc. |
| `ramp`  | 4,564 | interchange ramps (`motorway_link`) |

The five named interstates are geographically verified in the QA map
(`../../../network_validation_2023/FINAL_FIGURES/i95_context_map/freeway_network_qa.png`).

## Files

| File | What it is |
|------|-----------|
| `freeways_network.xml.gz` | MATSim v2 network, ONLY the 9,845 freeway+ramp links + their 9,344 nodes (EPSG:26985, corrected 65 mph freespeeds). Loadable standalone in Via. |
| `freeways_events.xml.gz` | Corrected run's events filtered to `entered link` / `left link` (+ `vehicle enters/leaves traffic`) on the selected links only. ~187 MB, valid MATSim events XML. |
| `freeways_link_ids.txt` | The 9,845 selected link ids, one per line. |
| `freeways_link_tags.csv` | link_id → `freeway_tag`, osm_name, highway class, freespeed, capacity, length, from/to nodes. |
| `layers/freeways.shp` | The selected links as lines, attribute `freeway` = the tag above (color by this in Via/GIS). |
| `layers/bmr_counties.shp` | 6 BMR counties (background). |
| `layers/aadt_stations.shp`, `aadt_stations_i95.shp` | AADT count stations (reference overlay). |

**Events:** 22,823,986 movement events kept — 11,400,717 `entered link` + 11,400,854 `left link`
(balanced) + 11,280 `vehicle enters traffic` + 11,135 `vehicle leaves traffic`. **0 orphan links**
(every link referenced in the events exists in the subnetwork). 9,561 of 9,845 links carry traffic;
the 284 with none are minor/dangling ramps with no resident trips.

## Get Via

Download from **https://www.simunto.com/via/**. Via offers a free academic/research license — request
it with your UMD address (`rtomal@umd.edu`), or use the size-limited free edition.

## Load & style

1. Via → **New visualization**.
2. Add the **network**: `freeways_network.xml.gz` (CRS EPSG:26985 auto-detected).
3. Add the **events**: `freeways_events.xml.gz`.
4. Two ways to color the links:
   - **Color → speed** — Via computes link speed from enter/leave timestamps; use a diverging red→green
     scale to **see congestion** (red = slow, green = free-flow at the corrected 65 mph).
   - **Color by `freeway_tag`** — load `layers/freeways.shp` and color by the `freeway` attribute to
     **see the system** (I-95 / I-695 / I-83 / I-70 / I-895 / other_freeway / ramp each a distinct color).
5. Set link **width → volume** so busy links render thicker.
6. Set the **time window to 05:00–22:00** to cover the AM/PM peaks.
7. **Zoom to an interchange** (e.g. **I-95 × I-695** at the NE, or **I-70 × I-695** on the west) and
   press **Play** — you'll watch vehicles transfer from one freeway to another across the ramps.

### Shapefile overlays (`layers/`)
Add `bmr_counties.shp` first (no fill, grey outline, sent to back), then the network+events, then
`freeways.shp` (color by `freeway`) and optionally `aadt_stations.shp` (size by `obs_AADT`, color by
`relerr_pct`) on top.

## Honest caveat (state this on the slide)

This is a **resident-trip simulation** — only trips by synthetic residents of the modeled region are
on the network; **long-distance / external through-traffic is not added**, so the freeways are
**under-loaded and run near free-flow**. The animation faithfully shows congestion **timing and
location** (where/when links slow relative to each other) but **not realistic congestion *levels***.
Don't read absolute volumes/speeds as validated traffic.

## Alternative: full regional context (heavier)

Load `../output_base/base_speedfix/output_network.xml.gz` + `output_events.xml.gz` (~1 GB) instead to
see the freeways among all roads; filter to these links using `freeways_link_ids.txt`.
