# Adding cost-responsive mode shift for the I-695 congestion-pricing study

Deep-research synthesis (web fan-out → fetch → 3-vote adversarial verification, 2026-06-30). The problem:
our Apollo mode-choice model's price/value-of-time coefficient is ≈0 (unidentifiable from RTS RP data —
generalized cost is collinear with distance, no exogenous cost variation), so it cannot produce mode shift
when a toll is added. Research recommendation, in three moves:

## 1. Fix the price coefficient from a Value-of-Time (don't leave it at zero)
- VOT is the ratio of the time and cost coefficients in linear utility: `VOT = β_time / β_cost`, so an
  asserted VOT + the (identified) time coefficient pins down the missing cost coefficient:
  **`β_cost = β_time / VOT`**. Cost is conventionally a single generic coefficient across modes. *(high
  confidence; USDOT 2016 VTT guidance + UK DfT TAG.)*
- **US VOT figure:** USDOT recommends valuing **local** personal travel time at **50% of median household
  hourly income = $13.60/person-hour (2015$)** (from $56,516 median ≈ $27.20/hr). Escalate to 2017$ (~$14/hr)
  and **segment by trip purpose/income**.
- **Baltimore-specific:** the Baltimore Metropolitan Council's own **FHWA TMIP peer review** explicitly
  flagged *"distribution of value-of-time"*, *"direct comparison of toll alternatives and transit"*, and
  *"income and VOT differences between Baltimore and Washington"* as required-but-missing for pricing
  analysis, and recommended toll response be modeled through **BOTH mode and route choice with VOT
  segmentation** (truncated log-normal per-person VOT + VOT-segmented assignment, as in Houston H-GAC ABM).
- Optional but ideal: strengthen identification with a small **stated-preference (SP) survey** jointly
  estimated with the RP data — SP supplies the exogenous cost variation the RP data lacks.

## 2. Preserve the RTS-validated base shares — re-calibrate the ASCs
After imposing the VOT-implied `β_cost`, the base-year mode shares will move. Restore them with the **same
per-purpose ASC re-calibration** we already built (`asc += ln(target/predicted)` to the RTS shares). This is
the canonical model-transfer/recalibration procedure: keep the new (correct-signed) cost sensitivity, shift
only the constants so 2017 base shares are reproduced. The price *elasticity* is now non-zero; the base
*shares* are unchanged.

## 3. Implement the shift via an OUTER skim-feedback loop (not MATSim-internal mode choice)
- **Preferred:** MATSim runs the tolled scenario → exports tolled+congested travel **times/costs (skims)** →
  **MITO re-runs its repaired, cost-elastic mode choice** on those skims → MATSim re-assigns the new modes.
  Iterate to convergence. This keeps the rich per-purpose/socio Apollo model as the mode-choice engine.
- **Why not** copy the MNL cost coefficient into MATSim's internal SubtourModeChoice scoring: estimated
  discrete-choice parameters **do not map one-to-one** onto MATSim's scoring, and MATSim's best-response
  selection will **not reproduce the estimated elasticity** unless frozen/deterministic Gumbel pseudo-errors
  are added. Route diversion + departure-time shift still happen inside MATSim (via VOT + roadpricing); mode
  shift is resolved in the outer loop.

## 4. Validate the resulting elasticity
Sanity-check against literature: real MATSim toll studies show **modest, commute-concentrated** mode shift —
e.g. the NYC CBD cordon MATSim study found **−1.63% car / +0.77% transit**. Target plausible arc-elasticities
of transit demand w.r.t. auto cost; don't expect large shifts.

## Concrete plan for our pipeline
1. Pick VOT (USDOT $14/hr 2017$, segment by purpose; optionally income). Convert to our gc units (gc is in
   minutes; `β_gc` becomes the per-minute marginal utility, and the toll $ enters gc via `$/VOT → minutes`).
2. Set `β_gc` (currently ≈0) to the VOT-implied negative value in the Apollo coefs; re-run
   `05_calibrate_asc_perpurpose.py` so the per-purpose ASCs re-absorb the level → base shares preserved.
3. Tag I-695 links; apply the MATSim **roadpricing** toll (time-of-day) in the policy run; set MATSim's
   `marginalUtilityOfMoney` + a car VOT so **route diversion + departure-time** respond to the toll.
4. Wire the **MITO↔MATSim skim feedback**: tolled/congested skims → MITO mode choice → MATSim. Iterate.
5. Compare base vs priced: link volumes/speeds on I-695 + diversion routes, mode shares, departure-time
   spreading, toll revenue; validate mode shift magnitude vs the elasticity benchmark.

### Key sources
- USDOT, *Revised Departmental Guidance on Valuation of Travel Time* (2016).
- UK DfT TAG, *Bespoke Mode-Choice Models* (VOT = β_time/β_cost).
- FHWA TMIP, *Baltimore Metropolitan Council Model Peer Review* (VOT segmentation for pricing).
- *Agent-based Simulation Evaluation of CBD Tolling: NYC* (arXiv:2402.10834) — MATSim roadpricing scoring `+ β_m·τ`, −1.63% car/+0.77% transit.
