# ABIT ↔ MATSim congested-skim feedback loop

`run_feedback_abit.py` — MSA orchestrator (adapted from `Updated MATSim/code/run_feedback.py`), demand
step swapped from the tour-based apply to **ABIT**.

## Loop (per outer iteration k)
1. **demand** — `RunAbitMarylandLos` reads the CURRENT congested car-time skim via the property
   `abit.skim.traveltime.file` (iteration 1 = free-flow MITO `traveltime_auto.omx`); then
   `validation/build_studyarea.py` → `output/matsim_population_abit_bmr.xml.gz` (full-MSTM 10% → BMR
   subarea cut).
2. **assign** — MATSim `de.umd.matsim.RunBaltimore` on that population (Baltimore network + PT).
3. **extract** — `Updated MATSim/code/skim_from_events.py` → realised congested zone-to-zone auto skim.
4. **blend** — MSA `skim_k = (1−1/k)·skim_{k−1} + (1/k)·new_k`; written back to the working skim path.
5. **gap** — mean relative skim change on changed cells; stop when < 0.03 and k ≥ 2.

Congestion is reported vs a network-consistent free-flow baseline (`freeflow_skim.py`, all car links at
freespeed, same Dijkstra) — the apples-to-apples reference (the MITO skim is a different source).

## Usage
    python code/run_feedback_abit.py [outer=3] [inner=5] [sample_fraction=0.03] [toll=0]

- `toll` > 0 → passed to ABIT `MarylandFullModeChoice.setToll()` (via `auto.toll`). MATSim I-695
  road-pricing is a **documented hook** (RunBaltimore takes no road-pricing arg yet; add a
  `roadpricing.xml` on the I-695 links + enable the RoadPricing module for the pricing scenario).
- Disk is freed between iterations (prior iter dir + interim MATSim plan dumps dropped).

## Config change (item 1)
`MarylandLosDataReader.readSkims` reads `abit.skim.traveltime.file` (fallback `car.time.omx.file`), so
the loop points ABIT at the congested skim each iteration. The DISTANCE skim stays fixed.

## Base (toll=0) 3-iteration test — CONVERGING
sample 3%, 5 MATSim inner iters. gap trajectory **0.082 → 0.040 → 0.033** (decreasing → converging to
tol 0.03). Congested peak times ROSE vs free-flow network baseline (44.3 min): **48.0 / 47.4 / 47.3 min
(+8.5% / +7.0% / +7.1%)**; 55% of on-network OD pairs >5% slower than free-flow.
