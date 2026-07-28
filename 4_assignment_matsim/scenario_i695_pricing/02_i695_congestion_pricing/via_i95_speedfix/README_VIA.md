# Visualizing the I-95 corridor in Via (Simunto) — CORRECTED-network run

This folder is a **lightweight, I-95-only** package extracted from the **corrected** MATSim base
run (`output_base/base_speedfix/`). Via loads a network + an events file and animates link
volumes/speeds over the day. The full regional events file is ~1 GB and shows the whole 6-state
region; this package is a self-consistent subnetwork + filtered events pair so Via loads in seconds
and shows just the John F. Kennedy Memorial Highway (I-95) corridor.

> **This is the CORRECTED-network build.** The freeway freespeeds in the base network were fixed —
> I-95 links now carry a realistic **29.06 m/s (65 mph)** freespeed. The earlier package in
> `../via_i95/` was built from the **broken** network where these same links were capped at
> **20.99 m/s (~47 mph)**, which artificially depressed corridor speeds. Use THIS package for the
> presentation; the old one is kept only for comparison.

## Files

| File | Size | What it is |
|------|------|-----------|
| `i95_link_ids.txt` | 2 KB | The 288 I-95 corridor link ids, one per line (NB+SB). Same corridor as before. |
| `i95_network.xml.gz` | 18 KB | MATSim v2 network with ONLY the I-95 links + their nodes (EPSG:26985). Loadable standalone in Via. Freespeeds = **29.06 m/s (65 mph)** on the mainline. |
| `i95_events.xml.gz` | 4.4 MB | The corrected run's events filtered to `entered link` / `left link` on I-95 links only. Valid MATSim events XML. |

**Corridor:** 288 links, 317 nodes. Identified as OSM name = `John F. Kennedy Memorial Highway`
PLUS the I-95 seed links, **excluding** the parallel `Express Toll Lanes` / `I-95 Express Toll
Lanes`. (Identical corridor to `../via_i95/` — only the underlying run changed.)

**Events:** 698,422 movement events kept (349,211 `entered link` + 349,211 `left link`, perfectly
balanced). **All 288 links carry traffic.** There are 0 `vehicle enters/leaves traffic` events on
I-95 links — trips begin/end on local streets and only *pass through* I-95, which is expected.
**Self-consistent: every link referenced in the events exists in the subnetwork (0 orphans).**

## Get Via

1. Download Via from **https://www.simunto.com/via/**.
2. Via offers a **free academic / research license**. You are at UMD (`rtomal@umd.edu`) —
   request the academic license from the Simunto site (or run the free edition, which is
   size-limited but more than enough for this 18 KB network + 4.4 MB events pair).

## Load this package

1. Open Via → **New visualization** (or File → New).
2. Add the **network**: `i95_network.xml.gz`.
3. Add the **events**: `i95_events.xml.gz`.
4. Via auto-detects the CRS (EPSG:26985) from the network attributes and draws the corridor.

## Recommended styling for the presentation

- Set link **coloring → speed** (Via computes link speed from enter/leave timestamps and link
  length). Use a diverging scale: **red = slow → green = free-flow**. Because the freespeeds are
  now correct (65 mph), free-flow links render green at realistic speeds rather than being capped
  at the old ~47 mph ceiling.
  - Optionally also try **coloring → volume** (vehicles/hour) to show where flow concentrates.
- Set link **width → volume** so busy links are visually thicker.
- Set the **time window to 05:00–22:00** to cover the daytime peaks (the events run from ~00:15
  into the next morning; the AM/PM peaks are inside this window).
- **Zoom to the I-95 corridor** (it fills most of the frame since nothing else is loaded).
- Press **Play** to animate the day. Adjust playback speed as needed.
- Use **File → Export snapshot / movie** (PNG or video) for the slides.

## Honest caveat (state this on the slide)

This is a **resident-trip simulation** — only trips made by synthetic residents of the modeled
region are on the network. **I-95 through-traffic (long-distance / external trips) is not yet
added**, so the corridor is **under-loaded and runs near free-flow**. The animation faithfully
shows **congestion *timing* and *location*** (where and when links slow down relative to each
other) but **not realistic congestion *levels***. Do not read absolute volumes/speeds as
validated I-95 traffic. (The network fix corrects the free-flow *speed ceiling*; it does not add
the missing through-traffic.)

## Alternative: regional context (heavier)

To see I-95 in its full regional setting, load the FULL files instead:

- Network: `../output_base/base_speedfix/output_network.xml.gz`
- Events: `../output_base/base_speedfix/output_events.xml.gz` (~1 GB — Via can handle it but
  loads slowly and uses a lot of RAM)

Then in Via filter/select to the I-95 links using the ids in `i95_link_ids.txt`, or just pan to
the corridor. Use this only when you need surrounding roads for context; otherwise the
lightweight pair above is faster and cleaner.

---

## Shapefile overlay layers (`layers/` folder)

These are GIS layers to load ON TOP of the network+events in Via (all EPSG:26985, aligned with the
network — unchanged from the `../via_i95/` build):

| file | geometry | use |
|------|----------|-----|
| `layers/aadt_stations.shp` | points (3,794) | all AADT count stations — attrs: `obs_AADT`, `model_vol`, `GEH`, `relerr_pct`, `road`, `facility`, `is_i95` |
| `layers/aadt_stations_i95.shp` | points | just the I-95 corridor stations (highlight subset) |
| `layers/bmr_counties.shp` | polygons (6) | the BMR county background for context |
| `layers/i95_corridor.shp` | lines (288) | the I-95 corridor highlighted (NB+SB) |

### Add them in Via
1. In Via: **Layer ▸ Add layer ▸ Shapefile** (or drag the `.shp` into the layer panel). Add `bmr_counties.shp` FIRST (as background), then the network+events, then `aadt_stations.shp` and `i95_corridor.shp` on top.
2. **Style the AADT stations:** size the point marker by `obs_AADT` (bigger = busier count) and color by `relerr_pct` (red = model under, blue = over) — so you SEE, at each count station, how the simulation compares. Turn on labels = `obs_AADT` if useful.
3. **Style the counties:** no fill + a light grey outline, sent to the back, for context.
4. **Style the I-95 corridor:** a bold color line so it stands out against the rest of the network.
5. To show only the I-95 count stations, load `aadt_stations_i95.shp` instead (or filter `aadt_stations` where `is_i95 = 1`).

Note: if your Via build prefers GeoPackage over shapefile, the same layers are in
`network_validation_2023/qgis/*.gpkg`; but the shapefiles here are rebuilt with corrected
EPSG:26985 geometry.
