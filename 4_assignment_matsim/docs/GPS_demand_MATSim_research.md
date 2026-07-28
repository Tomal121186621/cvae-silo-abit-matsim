# Simulating a GPS person-trip dataset in MATSim & benchmarking vs our resident-only model — research findings

**Verdict: feasible, with direct published precedent.** (Deep research 2026-07-06; 23 sources, 22/25 claims confirmed.)

## The critical distinction: data granularity
Only DISAGGREGATE per-trip/per-trace data can seed a MATSim population:
- **CAN seed MATSim:** INRIX Trips (per-trip waypoints/paths), **Replica** (activity-based per-trip table w/ O,D,mode,purpose), **raw mobile-device trajectories** (GPS/LBS trip rosters).
- **CANNOT (aggregate only):** StreetLight Volume, INRIX/TomTom **OD matrices** — these are AADT/OD totals, not individual agents.

## Proven conversion methods
- **(A) Activity-diary reconstruction** — infer home/work/other + start/end times → MATSim population (Barcelona CDR→MATSim, TR-A 121, 2019).
- **(B) Direct raw-trace** — place sightings on the network, connect by legs, simulate; calibrate departure times with **Cadyts link counts** (Zilske, TU-Berlin).
- **Eqasim** — documented open-source raw-data→MATSim pipeline; has a **"synthetic gates as hubs"** mechanism to inject boundary-crossing demand (natural for I-95 cordon).

## The on-point precedent — Barcelona (our exact problem, demonstrated)
CDR→MATSim, **resident-only**, expanded to a 10% sample, validated **GEH<10 on 9 of 11** city-entrance counts. **The 2 failures were exactly the through-traffic/freight-dominated corridors** the resident demand excluded — mirroring how our resident-only SILO/ABIT under-predicts I-95 through-traffic.

## Through-traffic isolation (our I-95 gap) — established workflow
DOT/MPO method (MAG Phoenix, TxDOT): GPS waypoints → determine trip ends → **filter external trips** → map-match → expand to classification counts. **Replica models pass-through travel as a separate stream** (ready-made through component). Cell-based data (device IDs persistent 1 month+) reliably flags visitor/through trips.

## The key risk — expansion, not penetration
GPS captures only **~0.5–2% of passenger AADT** (LBS 12–20%, cellular 15–25%, truck GPS ~11%). Must **expand/calibrate to ground counts (AADT/AVMT), NOT penetration rates** (FHWA: passive data is not a random sample; count-based expansion is far better). Use IPF to volume marginals or Cadyts link-count calibration inside MATSim.

## Comparison framework (designed — RQ5 not directly cited)
Hold the **same network + same assignment/scoring** constant, vary **only the demand**; compare link volumes via **GEH / %RMSE against shared AADT**; read the **GPS-minus-resident residual on freeway links as the through-traffic contribution**; overlay time-space/trajectory diagrams. (This design follows the Barcelona validation logic but is not itself a cited protocol.)

## Strongest leads for UMD
- **UMD's own MDLD pipeline** (arXiv 2301.08660, Yang et al., TRR 2024, UMD-affiliated) — Maryland Mobile Device Location Data → multimodal trip rosters → map-match → **expand/calibrate to AVMT & AADT**. This is *literally our region + pipeline, from your own institution.*
- **CATT Lab** (you already use it for NPMRDS) — INRIX partner; route to INRIX Trips.
- **Replica** — check UMD/MDOT license; its separate pass-through stream is the easiest through-traffic source.

## Don't rely on (refuted in verification)
- Molloy et al. Swiss GPS-panel→MATSim claims (split 1-2).
- StreetLight's self-reported R²=0.98 volume validation (0-3).

## Open gaps
Access/cost/academic-licensing/IRB for disaggregate INRIX Trips / Replica per-agent / raw mobile in Baltimore not established; whether Replica delivers true per-agent (vs tract-summarized) records; the exact citable comparison protocol must be designed.
