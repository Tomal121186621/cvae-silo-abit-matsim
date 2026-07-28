# TRB Peer Review — SILO Maryland Fork (engine changes)

**Scope:** custom calibration/re-anchor/occupation models + thread fixes in the Maryland fork of
`/Users/tomal/Documents/SILO Simulation/silo-master`.
**Posture:** strict, skeptical, read-only. Findings cite `file:line` with a concrete failure mode.
**Reviewer verdict:** the code is materially sound and the concurrency fix is correct. No CRITICAL
defects found. The most important issue is a **methodological coupling (MAJOR)**: the re-anchor
clones lose their jobs, which the occupation model then re-labels as non-employed, so employment is
systematically perturbed in the very year that feeds MITO/ABIT. Several MINOR correctness and
bookkeeping issues below.

---

## What's solid (verified, not just asserted)

1. **Concurrency fix is correct and complete.** `HouseholdDataManagerImpl.adjustIncome` (line 314) and
   `JobMarketUpdateImpl` (line 87) both switched `cachedService()` → `fixedPoolService(numberOfThreads)`.
   `ConcurrentExecutor.execute()` calls `service.shutdownNow()` in a `finally`
   (`.../util/concurrent/ConcurrentExecutor.java`), and a **new** executor is constructed each call, so
   pools do not accumulate across years. The old cached pool, fed ~12M tasks via `invokeAll`, spawned a
   thread per concurrently-runnable task and hit the OS ceiling — the described `unable to create native
   thread` OOM. The fix genuinely bounds and reclaims threads. **No remaining unbounded thread creation.**

2. **No data race in the parallel income task.** `IncomeAdjustment.call()` writes only `person.setIncome()`
   on its own distinct `Person`; the shared `currentIncomeDistribution`/`initialIncomeDistribution` arrays
   are read-only inside the task. Each `RandomizableConcurrentFunction` seeds its own RNG. Clean.

3. **Auto-ownership ASC reconstruction is mathematically exact.** In `MaryLandUpdateCarOwnershipModel.baseExpUtil`
   (lines 128–132) the UEC table stores `P(k)=util[k]·P(0)` and `P(0)=1/(Σutil+1)`, so
   `p0 = 1−(p1+p2+p3) = P(0)` and `p_k/p0 = util[k]` recovers the exact exp-utilities. The ASC update
   `delta_k += ln(target_k/pred_k)` (line 187), iterated 25× then frozen (line 80–83), is the standard
   logit-constant calibration and converges toward the ACS target shares. Direction is correct.

4. **Per-state levers are applied once, to the right rate, non-compounding.**
   - birth: `birthProb *= birthScaler(state)` once per candidate — `BirthModelImpl.java:97`.
   - marriage: `marryProb *= marriageScaler(state)` once per person — `MarriageModelMstm.java:252`.
   - income: growth factor applied once inside the per-person task — `IncomeAdjustment` return / `HouseholdDataManagerImpl.java:322`.
   - employment: participation lever re-measures current vs target **every year from a frozen base**
     (`EmploymentModelImpl.java:69–75`), so it self-corrects rather than compounding.
   None of these multiply a scaler onto an already-scaled state carried across years.

5. **Occupation age bands are gapless and non-overlapping.** `UpdateOccupationModelMstm.endYear`
   (lines 92–112): `age<6`→TODDLER; `age≥62`→RETIREE (tested before the student band); `6≤age≤35`→student/unemployed;
   `36≤age≤61`→UNEMPLOYED. Every non-employed age maps to exactly one bin. The stochastic draw
   `random.nextDouble() < pStudent` (line 102) with per-age ACS shares is correct probability semantics,
   and the `getOrDefault` fallbacks (0.97 for ≤18, 0.0 for the 19–35 map) are consistent with the table.

6. **Re-anchor preserves household count and moves the marginal in the intended direction.**
   Each `swap()` removes one household and adds one clone (net 0). The over/under selection
   (`reanchorRace` lines 250–255, `reanchorHhClass` lines 286–291) always removes from the
   most over-represented class and clones from the most under-represented, gated by `GAP_STOP=0.005`,
   so passes are monotone toward target and bounded by `budget`. `swap()` correctly reuses the freed
   dwelling: `removeHousehold` vacates and lists `dd`, then `moveHousehold(clone,-1,dd)` removes it from
   the vacancy list and sets the resident (`MovesModelImpl.java:346–354`) — no vacancy double-count, no leak.
   `duplicateHousehold` does **not** pre-register the clone (`HouseholdDataManagerImpl.java:389–397`), so the
   explicit `addHousehold`/`addPerson` in `swap` (lines 232–233) are **not** a double-add. Model ordering
   is correct: reanchor → occupation → car-ownership (`ModelBuilderMstm.java:157/167/174`, executed in list
   order by `Simulator.finishYear` line 121).

---

## MAJOR

### M1 — Re-anchor clones lose all jobs; the occupation model then re-labels their workers as non-employed, biasing employment **in the output year that feeds MITO/ABIT**
**Where:** `CompositionReanchorModelMstm.swap()` line 230 (`duplicateHousehold`), interacting with
`HouseholdDataManagerImpl.duplicateHousehold` (Javadoc lines 380–386: "…jobs and schools are **not**
copied"), and `UpdateOccupationModelMstm.endYear` lines 87–116.

**Failure mode.** Within a simulation year the employment `EventModel` runs during `processEvents`
(`Simulator.java:101–118`), **before** the annual `endYear` listeners. The re-anchor then runs in
`endYear` and replaces households with clones whose persons have `jobId = 0` (jobs are deliberately not
copied). Immediately after, `UpdateOccupationModelMstm` (registered next) sees `jobId == 0` for those
cloned workers, does **not** skip them (line 87 only skips `jobId > 0`), and overwrites their occupation
to UNEMPLOYED/STUDENT/RETIREE by age. Net effect for that year's written `pp_<year>.csv`: every worker
who lived in a removed household is gone, and the clone that replaced them contributes **zero** employed
persons. Employment can only be rebuilt by *next* year's employment model — but a *fresh* batch of jobless
clones is generated every year, so the depression is **persistent, not transient**.

The magnitude is not hypothetical: CLAUDE.md records `race=243667, income=51414, hhSize=24122 swaps` in
the first year. Hundreds of thousands of clones per year lose their jobs after the employment model has
already run.

**Why it matters for the paper.** The 2023 population handed to MITO/ABIT is the post-re-anchor,
post-occupation snapshot. HBW trip generation keys off EMPLOYED. If re-anchor strips jobs from a
non-trivial share of workers in 2023, work-trip volumes are understated at the source — directly relevant
to a congestion-pricing study. Note also that the `participationScaler` (PA/WV = 1.12,
`calibration_by_state.csv`) may be partly *compensating for this artifact* rather than for genuine ACS
under-participation, since it inflates the employment target that the year-end clone-stripping then eats
into. That makes the participation "calibration" partly circular.

**Fix.** In `swap()`, after `moveHousehold`, re-assign employment to the clone's workers to match the
source household (or run the employment/job-matching step once more over clones before writing output).
Minimally, have `UpdateOccupationModelMstm` treat "clone of an employed person" as employed, or run the
re-anchor **before** the employment event model within the year so employment can re-hire the clones in
the same year. At a minimum, quantify the in-year employed-count delta caused by re-anchor and confirm the
`participationScaler` is not silently absorbing it.

---

## MINOR

### m1 — Person totals are not conserved by the income and size passes (and by 4+ race swaps)
**Where:** `reanchorRace` lines 260–267 and `reanchorHhClass` lines 295–301.
The race pass matches on **size class**, not exact size; class 3 is "4+", so removing a size-8 household and
cloning a size-4 one changes the person count while claiming to preserve it (comment line 39,
"person count ~preserved"). The income and size passes (`reanchorHhClass`) match only on **race**, so the
clone's size differs from the removed household's — every income swap perturbs the person total. Household
count is preserved; person count drifts. This is partly masked by the population control totals but means
the re-anchor is not population-neutral as documented. **Fix:** match income swaps on size class as well
(or draw a clone whose size equals the removed household's), or explicitly reconcile person totals after
the passes.

### m2 — Income and size passes fight each other (bounded oscillation)
**Where:** `endYear` lines 149–163. The income pass (matched on race only) disturbs size; the size pass
(matched on race only) disturbs income. They run once each per year with the size pass "cleaning up" size,
but the size pass itself re-disturbs income. Convergence relies on the churn budget being small; there is
no joint check that both marginals ended within tolerance. **Fix:** iterate the two passes to a joint gap
criterion, or match each pass on the *other two* attributes so it only moves its own marginal.

### m3 — Household "race" is taken from the first-listed member, not an explicit householder
**Where:** `raceIdx` lines 208–215. The loop returns on the first person in the `LinkedHashMap`
(insertion order). For a mixed-race household this tallies the first-inserted member's race, which is only
the householder if the synthetic population happens to insert the head first. It is deterministic and
preserved through cloning, but a mixed-race household can be mis-binned relative to the ACS
householder-race convention the targets use. **Fix:** classify by `PersonRole` head/reference person, not
map-iteration order.

### m4 — `CalibrationConfig.active` ignores `participationScaler`
**Where:** `CalibrationConfig.java:108`. `active` is set from birth/marriage/income/auto only; a config
that sets *only* `participationScaler` logs "OFF (free-run)" even though the lever is live (getters return
the loaded value regardless). Cosmetic/log-only — the lever still applies — but misleading in run logs.
**Fix:** include `!participation.isEmpty()` in the `active` disjunction.

### m5 — Occupation is stochastically re-rolled every year → person-level flicker
**Where:** `UpdateOccupationModelMstm.endYear` line 102. A 25-year-old non-worker is STUDENT with p=0.276
**re-drawn each year**, so the same individual flips STUDENT↔UNEMPLOYED across years. Harmless for the
cross-sectional marginal being validated, but it destroys any longitudinal/panel consistency and injects
year-to-year noise into MITO's student vs non-student trip assignment for the same person. **Fix:** only
draw for persons crossing into the band, or persist the drawn status unless age moves them out of the band.

### m6 — Top income category collapses 200k+ into the 150–200k auto-ownership cell
**Where:** `getIncomeCategory` lines 92–100 returns `incomeCategories.length` (=12) for income ≥ 200000,
then `baseExpUtil` line 123 clamps `min(12,…)` and indexes `incomeCategory-1 = 11`, the same cell as the
150000–200000 band. All households above $200k share the $150–200k auto utilities. Likely immaterial given
the ASC recalibration, but it is an undocumented ceiling. **Fix:** confirm the UEC's top income bin is
intended to be open-ended, or extend the table.

---

## Claims I could NOT substantiate from code (not necessarily wrong — out of scope of a static audit)

These are **empirical run outputs**, not encoded in the source, so this code review cannot confirm or
refute them. Flagged only so the paper does not cite them as code-verifiable:

- **"auto TV 0.21→0.02", "occ 9.6–13.6pp → 2.5–6.2pp", the 22→15→6→5→3 failing-cell progression**
  (CLAUDE.md): live in the validation scorecard CSVs under `Updated SILO/validation/…`, not in the engine.
  The code makes them *plausible* (the ASC calibration targets `auto_target_shares.csv`; the occupation
  model directly restores STUDENT/RETIREE), but the magnitudes must be checked against the scorecard
  outputs, not asserted from the code.
- **"DC delta3=−0.95, WV delta3=+4.86"** (CLAUDE.md item 6): these ASCs are computed at runtime in
  `calibrateAscToTargets` and only emitted to the log (lines 191–195). Directionally consistent with the
  targets (`auto_target_shares.csv`: DC p3=0.039 low, WV p3=0.238 high → negative vs positive delta3), but
  the exact values are unverifiable without the run log. WV delta3 ≈ +4.86 is a very large constant (exp≈129),
  i.e. the UEC base badly under-predicts rural 3+-car ownership — worth a sanity note in the paper, since a
  frozen ASC that extreme is fragile to any composition drift (consistent with the acknowledged WV-autos residual).

---

## Bottom line
The engineering is honest and mostly correct: the thread fix is real, the ASC math is exact, the levers
are applied once and in the right place, and the occupation bands are clean. The one issue a reviewer
would press on is **M1** — re-anchor clones are job-stripped after the employment model has run, so the
employment field in the exact year exported to the travel model is biased, and the participation lever may
be masking it. That is fixable and should be quantified before the numbers are used in the pricing paper.
Everything else is MINOR bookkeeping/robustness.
