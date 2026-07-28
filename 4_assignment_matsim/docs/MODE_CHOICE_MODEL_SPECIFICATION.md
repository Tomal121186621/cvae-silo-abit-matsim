# The MATSim Mode Choice Model — Complete Specification
*(v17mc baseline configuration, 2026-07-12; all parameters verified against `RunBaltimoreToll.java`)*

## 1. Architecture: co-evolutionary choice

Mode choice is **not** a closed-form logit evaluated once. Each of the 298,236 agents carries a
memory of up to 5 complete day-plans. Every iteration:

1. **Propose** — 15% of agents receive a SubtourModeChoice mutation: one home-anchored tour
   (subtour) of a copied plan gets a new feasible mode. Another 15% get a ReRoute (new congested
   routes), 10% a TimeAllocationMutator draw (departure times shifted ±30 min).
2. **Execute** — every agent's *selected* plan runs in the queue simulation; car legs experience
   real congestion, spillback, and tolls.
3. **Score** — the executed plan is scored on *experienced* outcomes (Section 3).
4. **Select** — ChangeExpBeta (weight 0.60) keeps better-scoring plans with probability
   ∝ exp(Δscore); the worst plan is dropped when memory exceeds 5.

Innovation (steps 1) is disabled after 80% of iterations (it.32 of 40); the remaining iterations are
selection-only cleanup that discards failed experiments. Equilibrium = stationary shares under no
profitable deviation. The behavioral content therefore lives entirely in the **scoring function**.

## 2. Choice set and constraints

| Constraint | Value | Source |
|---|---|---|
| Modes | car, ride (car passenger), pt, walk, bike | ABIT universe |
| Car availability | persons with `autos = 0` or no license: car excluded (15.3% of persons; ABIT-mode seed recovers data inconsistencies) | population attributes (SILO joint demographics) |
| Walk feasibility | trips ≤ 2,000 m only | DistanceConstrainedPermissibleModes |
| Bike feasibility | trips ≤ 5,000 m only | same |
| Chain consistency | SubtourModeChoice `betweenAllAndFewerConstraints`: a car left somewhere must be retrieved; subtours respect vehicle continuity | MATSim standard |
| Tours, destinations, schedule structure | FIXED from ABIT (mode choice re-decides modes only; departure times move ±30 min) | upstream demand model |

## 3. The scoring function

For person *p* executing a day-plan:

```
S(p) = Σ_activities  0.78 · t_perform                                (utils; opportunity cost of time)
     + Σ_legs  [ ASC_m + β_m · t_leg ]                               (mode preference terms)
     + λ(p) · Σ  ( − fuel − fares − tolls )                          (person-specific money term)
```

### 3.1 Activity side
`performing = +0.78 utils/hr` against each activity's typical duration (home/work/shopping/other,
plus mapped escort/eat/errand/socialrec). Time spent traveling forgoes performing — this carries
car's entire time cost (car's β is normalized to zero), giving the clean identity
**VOT_car = performing / λ**.

### 3.2 Mode parameters (per-mode utility + operating cost)

| Mode | ASC (calibrated) | β time (utils/hr) | Monetary rate | Routing |
|---|---|---|---|---|
| car  | 0 (reference) | 0.00 (cost via performing) | $0.075/km fuel + link tolls | network (qsim, congested) |
| ride | (full-scale calibration in progress; subsample value was −4.10) | **0.00** (= car; see note) | $0.075/km (shared vehicle cost) | routed on car network at **congested car times**, teleported (adds no traffic) |
| pt   | (recalibrating; subsample +2.04) | −1.02 | $0.50/km fare | SwissRailRaptor on the mapped GTFS schedule |
| walk | (recalibrating; subsample −1.16) | −4.40 | — | teleported, 1.23 m/s, beeline factor 1.3 |
| bike | (recalibrating; subsample −4.06) | −2.345 | — | teleported, 3.1 m/s, beeline factor 1.3 |

**Ride time coefficient (structural finding, 2026-07-13):** originally ported as −1.11/hr (a
CAR_PASSENGER/SHARED_RIDE blend from bus-like published tables), making ride's total time disutility
2.4× car's. At full scale this congestion-amplified penalty crushed the switchable car↔ride margin —
measured ASC response ~1 pp/unit, ~17× weaker than logit — and would have multiplied every scenario's
congestion change into ride-share artifacts. Corrected to 0.00 (passenger time = driver time via the
performing channel), which matches ABIT's GC formulation where VOT divides only the money term.

Notes with provenance:
- β_pt = −1.02/hr and β_ride = −1.11/hr are the Maryland MNL time coefficients normalized against
  car (MODE_SCORER_MAPPING §3).
- Walk/bike β convert the source model's per-km penalties (−1.17/km walk, −0.28/km bike) into
  time-channel equivalents via teleport speed, because MATSim does not reliably score distance on
  teleported legs (documented in-code; the earlier distance-based port made walk a runaway attractor).
- Ride is deliberately routed at congested car times — a previous fixed-43 km/h teleport made ride
  congestion-immune and therefore a mode-choice sink (documented in-code).

### 3.3 The money term — income-dependent, following Cirillo exactly

```
λ(p) = 0.0245 · clamp( λ̃(I_p) / λ̃(I_median), 0.4, 2.5 )        [utils per 2023-$]
λ̃(I) = 0.525 − 0.002 · I_trip                                    [Bas Vicente & Cirillo 2017, MXL]
I_trip = (hhIncome_2016$ / 1.067) / (2.88 × 260)                  [survey-year $, income per trip]
```

- **0.0245 utils/$** ⇒ median VOT = 0.78/0.0245 = **$31.8/hr in 2023 dollars** = Cirillo et al.
  (2024) pre-pandemic Express-Lanes WTP ($26–28/h, midpoint $27 in early-2020 $) × CPI 1.18.
  Independently confirmed by Lin, Spissu & Cirillo (2025): baseline OL VTTS $26.38.
- **λ̃(I)** is the marginal utility of money from the Jara-Díaz–Videla quadratic utility
  V = β₁(I−c) + β₂(I−c)² + β₃TT estimated on the Maryland Capital Beltway SP (n=766):
  β₁ = 0.525, 2β₂ = −0.002 (their Fig. 1, mixed-logit column). Differentiation gives
  λ̃ = β₁ + 2β₂(I−c); the trip-cost term is dropped (<2% at observed costs).
- **Income per trip** is the paper's own transformation (2.88 trips/day × 260 working days);
  incomes are deflated from SILO's 2016$ to the survey's 2011$ scale.
- **Clamp [0.4, 2.5]** regularizes the quadratic's zero-crossing (λ̃ < 0 above ≈$196k/yr, outside
  the SP sample support); bounds match the demand model's precedent. Binds only above ≈$172k/yr.
- Median income computed live from the population (n = 298,236).

Resulting VOT gradient (examples): $20k household ≈ $18/h · $50k ≈ $24/h · median ($97k) ≈ $31.8/h
· $150k ≈ $56/h · ≥$172k ≈ $80/h (clamped). A $3.00 harbor toll ≡ 10 min of time at $18/h VOT,
5.7 min at the median, 2.3 min at the clamp.

### 3.4 Tolls
`org.matsim.contrib.roadpricing` link tolls fire person-money events scored through λ(p) — so toll
response is income-elastic by construction. Base scheme: the three existing MDTA harbor crossings
at $3.00 per directional crossing (2-axle E-ZPass MD, 2023 rates). The I-695 scenario adds its
scheme on top.

## 4. Calibration

- **Only calibrated parameters:** the four non-reference ASCs (car frozen at 0).
- **Targets:** the validated ABIT demand's mode shares — car 77.59 / ride 16.27 / walk 3.66 /
  pt 1.80 / bike 0.68 (%, trips).
- **Update rule (reference-corrected MNL re-anchor):**
  `ASC_m += ln(target_m/sim_m) − ln(target_car/sim_car)` — the car-deficit term is required
  because car is the frozen reference; omitting it (the original loop) under-steps by the full car
  gap per pass.
- **Procedure:** warm-started 30-iteration passes on a 60k-person subsample (2.0% traffic scale,
  flowCap 0.0201/storageCap 0.08), plans carried between passes so equilibration compounds.
- **Subsample result:** converged, worst gap 0.99 pp (car 76.6 / ride 16.7 / walk 3.9 / pt 2.4 / bike 0.4).
- **Full-scale transfer (v17mc, 40 it):** walk/bike transferred (<1 pp); car/ride did NOT
  (car 80.3 / ride 11.5) — the 2%-scale calibration never faced real congestion. Two warm full-scale
  passes measured the ride pathology (see ride note above) and motivated the structural fix; final
  full-scale ASC anchoring is running (warm 15-iteration passes from the equilibrated plans).

## 5. What the model inherits vs. decides

| Decided upstream (SILO/ABIT, demographically conditioned) | Decided in MATSim |
|---|---|
| who travels, tour frequency, destinations, activity durations, schedule skeleton, car ownership, incomes, home/work locations | mode per subtour, route, departure time (±30 min), all under congestion + tolls |

Joint demographic structure therefore *emerges* in outcomes: exposure to the tolled corridor comes
from SILO/ABIT's spatial sorting; alternatives from car availability and local transit supply;
cost sensitivity from λ(income). Not represented: pure preference heterogeneity conditional on
identical circumstances (age/gender mode-taste coefficients) and the usage-frequency VTTS skew of
Lin, Spissu & Cirillo (2025) — the latter is handled as a revenue-bracket post-analysis
(`make_revenue_bracket.py`).

## 6. Provenance summary

| Element | Source |
|---|---|
| Utility form for income effect | Jara-Díaz & Videla (1989) via Bas Vicente & Cirillo (2017, NTC2015-SU-R-09) |
| λ̃ coefficients (0.525, −0.002), income-per-trip transform | same report, Fig. 1 (MXL), p. 12 |
| VOT level anchor $31.8/h (2023$) | Lin, Spissu & Cirillo (2024, TR-A 182) pre-pandemic $27 × CPI 1.18; confirmed by Lin, Spissu & Cirillo (2025, RTE 114) |
| Mode time coefficients, operating costs | Maryland MNL port (MODE_SCORER_MAPPING.md) |
| ASCs | calibrated to ABIT-validated shares (this work) |
| Clamp [0.4, 2.5] | project demand-model precedent; sensitivity variant 0.25 |
| Sensitivities queued | VOT $27 (unadjusted), ~$36 (pandemic-period); frequency-VTTS revenue bracket |
