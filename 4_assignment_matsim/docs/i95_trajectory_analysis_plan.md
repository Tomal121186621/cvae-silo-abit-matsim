# I-95 Corridor Trajectory Analysis — Plan (from deep research, 2026-07-08)

Goal: from the **completed** resident-only MATSim base run (v7), extract, visualize, and profile the
agents that use I-95 — **before** the toll scenario — to set up the congestion-pricing equity story.

## Two complementary toolchains
1. **`matsim-tools` Python pipeline** (`pip install matsim-tools`, matsim-vsp/TU-Berlin) — the workhorse for
   reproducible, publication figures + the equity join. Integrates MATSim output with pandas/GeoPandas.
2. **Simunto Via** (ready-made GUI) — ingests `network.xml.gz` + `output_plans.xml.gz` + `output_events.xml.gz`
   natively (no conversion); animated vehicle trajectories + **select-link** to isolate corridor users.
   Free alternatives: **OTFVis** (`OTFVis -convert events network mvi` → pre-recorded movie, no re-sim) and
   **SimWrapper** (network link plots + experimental event viewer).

## The Python pipeline (5 steps)
**A — Identify I-95 links + route map.** `net = matsim.read_network('network.xml.gz')` → `net.nodes`, `net.links`
(link_id, from/to node, length, capacity, freespeed, + facility/road-type attribute cols). `net.as_geo()` →
GeoPandas LINESTRINGs; filter by road-type/facility attribute (and spatial bbox) to get the **I-95 link-ID set**;
`.plot()` for the corridor map. (Sanity-check against the AADT station→link matching already done.)

**B — Extract per-vehicle I-95 trajectories.** `matsim.event_reader('output_events.xml.gz', types='entered link,left link')`
streams events (generator, memory-safe). Keep events whose link ∈ I-95 set; group by vehicle/person; sort by time
→ each vehicle's ordered (link, enter_t, leave_t) sequence. **Corridor users = vehicles with ≥1 I-95 link event.**

**C — Time–space (distance–time) diagrams.** Per vehicle: cumulative distance along I-95 (Σ link `length`) vs event
time → one polyline per vehicle. Slope = speed; converging/steepening lines = queues/platoons/backward shockwaves;
flat-slow segments = bottlenecks. Facet by direction (NB/SB) and by peak period.

**D — Corridor flow analysis (Edie's generalized definitions).** Over a space–time region on I-95 compute
flow, density, space-mean speed → fundamental diagram + bottleneck detection. **Each region must be stationary +
homogeneous** to be valid. Also per-link hourly speed/volume profiles.

**E — Socio-demographic + OD profile (the equity table).** `matsim.plan_reader('output_plans.xml.gz', selected_plans_only=True)`
streams (person, plan); join corridor-user IDs → person attributes (income, race, age, hh size, autos, home zone)
+ plan activities (O/D coords, trip purpose). Build the incidence table: **who uses I-95, by income/race/age + OD**.

**⚠ Sample scaling:** demand is 10% (flowCapacityFactor 0.10) → multiply all **counts/flows by 10** (1/fcf).
Speeds, densities, shares, trajectories are per-vehicle and **not** scaled.

## Equity framing (precedents + what to expect)
- **Method precedent — MATSim-NYC** (arXiv 2008.04762): partition users by geography/income, quantify differential
  negative impact (37.3% Manhattan-resident vs 39.9% outside negatively impacted by the cordon). Executed/experienced
  plans give the per-agent welfare change.
- **Zurich cordon-charge MATSim** (TRR 2670-10): canonical disaggregated 24-hr incidence; ABMs capture departure-time
  shift + heterogeneous VOT that 4-step misses — exactly what our income-VOT model provides.
- **Expected finding to test:** uncompensated congestion pricing is **regressive** (low-income lose welfare, high-income
  gain); reversible mainly via **revenue recycling**. Distance-based + cordon schemes flagged "particularly regressive."
- **Toll mechanism (follow-on):** MATSim **roadpricing contrib** — per-vehicle toll on entering specified links,
  link/cordon/area/distance + time-dependent, converted to disutility via beta_money·toll. (Already scoped for I-695.)

## Deliverables → steps
(a) I-95 user **trajectory maps** → A + B (+ Via for animation).  (b) **time–space diagrams** → C.
(c) **socio-demographic + OD profile** → E.  (d) **corridor flow analysis** → D.

## Reuse in-repo
`Updated MATSim/code/skim_from_events.py` already parses MATSim events → build the I-95 pipeline on top of it.
Sources: matsim-tools (pypi/github matsim-vsp), Simunto Via docs, OTFVis apidocs, SimWrapper docs,
arXiv 2008.04762 (MATSim-NYC), TRR 2670-10 (Zurich), arXiv 2305.07318 (regressivity), arXiv 2402.10834 (roadpricing).
