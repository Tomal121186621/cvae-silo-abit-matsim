# Fully-loaded, count-calibrated I-695 network — design

**Goal.** Turn the resident-only MATSim base (v8) into a *fully-loaded* network whose simulated volumes
match observed **2023 AADT on freeways AND all roads** (not just the resident share), validated
**out-of-sample**, so the I-695 congestion-pricing (toll) run is realistically congested. Equity analysis
stays on the **resident** population.

**Why the resident base is not enough.** The ABIT resident demand only contains trips with at least one end
inside the Baltimore metro region (BMR). It therefore omits (a) **through / external** traffic (enters at one
regional gateway, leaves at another — e.g. I-95 N ↔ I-95 S bypassing downtown on I-695) and (b) the
**road-space effect of freight**. The resident-only base under-loads freeways by ~44% (`gap_decomposition.csv`,
freeway agg ratio ≈ 0.49). We add the missing demand, then calibrate it to counts.

**Cadyts?** Not available — the shaded `baltimore-matsim-1.0.jar` contains no `cadyts` classes and the pom
explicitly defers it (`<!-- cadyts contrib added in the calibration phase … -->`). Rather than add the
dependency and rebuild (the v8 base is currently reading the jar), we calibrate with **SPSA**, which needs
**no jar change** — it drives MATSim from outside via the seed scripts and an optional capacity file.

---

## 1. External / through-OD seed  (`code/seed_gateway_through_od.py`)

**Gateways.** 14 radial gateways are pre-computed in `network_validation_2023/calibration/gateways_2023.csv`
(rows with `external>0`). Each carries interior/boundary links `in_lid,in_tnode,out_lid,out_fnode`
(EPSG:26985), the **total** observed boundary AADT `cordon_aadt` (incl. trucks), the modeled resident volume
`cur_vol`, the per-gateway truck share `truck_frac`, and the gap to seed

$$\text{external}_g \;=\; \text{cordon\_aadt}_g \;-\; \text{cur\_vol}_g \quad(\text{bidirectional veh/day}).$$

ΣExternal = **474,157 veh/day**.

**Marginals.** Split each gateway's gap half in / half out (optionally × an SPSA scale $s_g$):

$$O_g = D_g = \tfrac{1}{2}\, s_g \,\text{external}_g .$$

**Impedance = shortest-path plausibility.** Deterrence between gateways $i,j$ is

$$D_{ij} = \exp(-\beta\, t_{ij}), \qquad i \ne j,$$

where $t_{ij}$ is the **network free-flow shortest-path travel time** from gateway $i$'s interior inbound node
to gateway $j$'s interior outbound node (`--impedance sptime`; `scipy.sparse.csgraph.dijkstra`, edge weight
`length/freespeed`, only the 14×14 gateway pairs are read). This is what makes a through trip take the corridor
it really would — opposite ends of a long freeway are *plausible* (low travel-time deterrence along that
freeway), whereas a Euclidean model would penalize them as "far". A `--impedance beeline` mode
($D_{ij}=\exp(-\beta\,\lVert x_i-x_j\rVert)$) is provided for the lightweight sanity test when the machine's
RAM is held by a running MATSim job. $\beta$: `8e-4`/s (sptime) or `2.5e-5`/m (beeline).

**Doubly-constrained Furness / IPF.** Iterate row/column balancing until the trip matrix $T$ matches both
marginals (no $i\to i$):

$$T \leftarrow T \cdot \frac{O}{\text{rowsum}(T)}, \qquad T \leftarrow T \cdot \frac{D}{\text{colsum}(T)} .$$

Row/column sums then reproduce the gateway marginals by construction, so each gateway's realised
`seeded_in + seeded_out = external_g`, and `seeded_through + cur_vol ≈ cordon_aadt` (reconstruction check,
`through_od_seed_report.csv`, max error ≈ 0%).

**MATSim emission.** Each through trip → agent id `ext_<n>`, `subpopulation="external"`, origin activity
`type="other"` anchored on the **entry boundary link** `link=in_lid[i]` (+ `cx/cy` fallback) → `<leg mode="car"/>`
→ destination activity on the **exit boundary link** `link=out_lid[j]`. Departures are drawn from the 2023
**TMAS weekday 24-h profile** (`tmas/station_profiles.csv`, `obs_h*`). Generated at the resident 10% sample and
appended to the base plan file. (`type="other"` is a scored activity in `RunBaltimoreToll`; agents with a car
leg get `carAvail=always`.)

---

## 2. Freight / commercial layer  (`code/seed_freight.py`)

`cordon_aadt` already **counts** trucks, so the through-OD already carries freight as vehicle counts. What it
misses is the **road space** a truck consumes (PCE ≈ 2 in congestion). This layer adds the PCE *uplift* as extra
background car-equivalent through-trips so truck-heavy freeways congest realistically:

$$\text{freight\_extra}_g = s_g\,\text{external}_g \cdot \text{truck\_frac}_g \cdot (\text{PCE}-1), \quad \text{PCE}=2.0,$$

distributed with the **same Furness** and impedance, emitted as `frt_<n>` / `subpopulation="freight"`. It is
**background** (no income, not equity population). The freeway volume-weighted truck share reproduces ≈ 6.8%
(cf. `gap_decomposition.csv` freeway commercial ≈ 6%). `--pce 1.0` disables the layer (freight then represented
only as its vehicle count in the through seed).

---

## 3. Station partition  (`code/select_calibration_stations.py`)

From `network_validation_2023/manual_check/station_link_match_audit.csv` (cleanly matched only:
`n_links>0`, `match_quality≠no_match`; 3,422 stations):

- **CALIBRATION** (shown to SPSA) = the **14 gateways** (forced in, boundary links + `cordon_aadt`)
  **+** a **facility-stratified, spatially-interleaved ~50%** sample. Within each facility group
  (Interstate/Freeway, Principal, Minor, Collector/Local) stations are sorted by a coarse 5 km spatial grid key
  and every other one is taken, so calibration and hold-out are geographically interleaved (not clustered).
- **HELD-OUT** (never shown) = the remaining cleanly-matched stations, **plus all ramps** (capacity fixed, not
  calibrated) for reporting.

Result: 1,175 calibration (incl. 14 gateways; freeway/principal/minor/collector = 111/170/294/600) vs 2,261
hold-out. Written to `calibration/spsa_{calibration,holdout}_stations.csv`.

---

## 4. SPSA calibration  (`code/spsa_calibrate.py` + `scenarios/02_i695_congestion_pricing/run_spsa_calib.sh`)

MATSim-NYC recipe (He, Chow & Ozbay, *A validated MATSim model for NYC*, arXiv:2008.04762); Spall (1992).

**Parameters** $\theta$ (kept small — SPSA cost is O(2) evals/iter independent of dimension):

- 14 per-gateway through-inflow **scales** $s_g \in [0.5, 2.0]$ (multiply `external` before Furness — corrects
  the resident-gap estimate per gateway);
- optional 3 **arterial capacity multipliers** $c_f$ (principal ∈[0.47,0.80], minor ∈[0.80,1.00], collector
  ∈[0.83,1.17]); freeway & ramp fixed at 1.0. **Off by default** (`SPSA_CAP_DIMS=0`) — enable only if freeways
  fit but arterials lag, since freeway loading should come from the gateway seed, not capacity.

**Objective** — facility-weighted %RMSE on the CALIBRATION stations:

$$f(\theta)=\sqrt{\frac{\sum_s w_{\text{fac}(s)}\left(\dfrac{\text{sim}_s-\text{obs}_s}{\text{obs}_s}\right)^2}{\sum_s w_{\text{fac}(s)}}},$$

$\text{sim}_s = \big(\sum_{\ell\in s}\text{vol}_\ell\big)\cdot\frac{1}{\text{flowCap}}$, weights
freeway 3 / principal 2 / minor 1 / collector 1. ΣGEH, %GEH<5 and corr² are logged too.

**SPSA update** (iteration $k$, two MATSim runs):

$$\Delta_k\sim\text{Bernoulli}(\pm1),\quad
\theta^\pm=\text{clamp}(\theta\pm c_k\Delta_k\,\sigma),\quad
\hat g_k=\frac{f(\theta^+)-f(\theta^-)}{2c_k\sigma}\,\Delta_k^{-1},\quad
\theta\leftarrow\text{clamp}(\theta-a_k\hat g_k),$$

$$a_k=\frac{a}{(A+k+1)^{0.602}},\qquad c_k=\frac{c}{(k+1)^{0.101}},$$

with $A\approx 0.1\times$ budget, step scale $\sigma=0.3$, $a=0.30$, $c=0.10$ (all env-tunable). $\theta$ is
clamped to its bounds each step; the best incumbent is saved to `runs/spsa/theta_best.json`.

**Each evaluation** = seed external (`sptime`) + freight with $\theta$'s scales → append to the base pop →
(optional) write a capacity network via `edit_network_capacity.py` → `run_toll.sh` with `WRITE=false` (disk-light:
modestats + linkstats only) → read linkstats → score. Runs are deleted between evals to free disk.

**Budget / tractability.** Runs on a **subsample** (`pop_sub50k.xml.gz`, sample 0.018, flowCap 0.0178) at
**reduced inner iterations (~40)**; ~10–20 SPSA iterations ⇒ ~20–40 short MATSim runs. Then a **single final
full-population run** at $\theta^*$ (v8 residents + seed at sample 0.10, flowCap 0.10, 64 iters, `WRITE=true`)
writes the calibrated network + linkstats for validation.

---

## 5. Out-of-sample validation  (`code/validate_holdout.py`)

Reuses `netval2023_common` (`load_linkstats` ×10, `geh`). Points `NETVAL_OUTDIR` at the final calibrated run and
reports **corr² / median GEH / %GEH<5 / %RMSE / mean rel-bias** on the **HELD-OUT** set and, side by side, the
**CALIBRATION** set (over-fit check), overall and by facility → `network_validation_2023/<SUB>/summary.csv`.
Close held-out vs calibration fit ⇒ the calibration generalised.

---

## 6. How the toll run uses the calibrated network (equity on residents only)

The final loaded plan file (`bmr_plans_v8_loaded.xml.gz` = v8 residents + `ext_*` + `frt_*`) and the calibrated
capacities load the network to observed AADT. The I-695 toll (`scenarios/toll_research/`, RoadPricing) is applied
on top of this realistically-congested base, so diversion/queueing respond to true volumes.

**Equity is computed on residents only.** `RunBaltimoreToll` keys car-availability off the presence of a car leg,
not a subpopulation attribute, so the background agents are identified by **id prefix**: all equity
post-processing (mode/route/toll-cost/accessibility by income group) **filters out agents whose id starts with
`ext_` or `frt_`**. The `external`/`freight` agents carry no income and never enter the equity tabulation; they
exist only to load the road. (A `subpopulation` attribute is also written for convenience but the id-prefix
filter is authoritative.)

---

## Files

| File | Role |
|---|---|
| `code/seed_gateway_through_od.py` | through-OD seed (Furness, sptime/beeline, `ext_` agents, reconstruction report) |
| `code/seed_freight.py` | freight PCE background layer (`frt_` agents) |
| `code/select_calibration_stations.py` | calibration vs held-out station split |
| `code/spsa_calibrate.py` | SPSA engine (θ, objective, gains, per-eval MATSim) |
| `scenarios/02_i695_congestion_pricing/run_spsa_calib.sh` | launcher (guards against a running assignment) |
| `code/validate_holdout.py` | out-of-sample corr²/GEH/%RMSE/bias, held-out vs calibration |
| `network_validation_2023/calibration/spsa_{calibration,holdout}_stations.csv` | station lists |
| `network_validation_2023/calibration/{through_od_seed,freight_seed}_report.csv` | seed sanity reports |
| `runs/spsa/{spsa_history.csv,theta_best.json}` | SPSA trace + calibrated θ* |

## Open items / flags
- **Boundary-link QA.** Two gateways are ramp-only / interchange edges (`RP` / `motorway_link`); anchoring on
  `in_lid/out_lid` handles them, but eyeball their placement before the final run.
- **Capacity classification** in `edit_network_capacity.py` reads `osm:way:highway`; confirm the speedcal network
  retains that child attribute before enabling `SPSA_CAP_DIMS>0`.
- **Sample consistency.** The subsample SPSA seeds external/freight at the subsample rate (`SPSA_SAMPLE`); the
  final build re-seeds at 0.10 to match the full v8 residents.
- Do **not** run SPSA (or rebuild the jar) while the v8 base is assigning — `run_spsa_calib.sh` aborts if it
  detects a running `RunBaltimore*`.
