# Consolidated Strict TRB Code + Figures Review — VAE → SILO → ABIT → MATSim

**Scope:** full pipeline code + publication figures for the I-695 congestion-pricing equity paper. Four independent skeptical reviewers (VAE, SILO, ABIT, MATSim+figures). MITO excluded per direction. Findings verified against source; coordinator added the income-VOT cross-check.

## Overall verdict
**The model *cores* are algorithmically sound — no fabricated logic, correct math throughout.** The problems cluster in three buckets:
1. **Overstated claims / framing** (fixable by honest rewriting) — the largest category.
2. **A few real modeling issues** that affect results (must fix or scope out).
3. **Figure integrity** (a strict TRB reviewer would reject several as presented).

---

## CRITICAL (must resolve before submission)

### CR-1 — The income-elastic toll engine is NOT in the model that generates the demand
- ABIT's operative base mode choice `ABIT/.../MarylandFullModeChoice.java:49` uses a **fixed VOT constant** — reads no income. The income-VOT MNL **does exist** but in a *separate* layer, `Tour Based MITO/code/apply/apply_plans.py:347` (`vot_from_income`, `tollM` arg), which is **not yet wired into the toll loop**.
- **Impact:** every "who bears the I-695 toll / income-elastic response" conclusion depends on the apply-layer being the operative toll-response model. As built, base demand (fixed VOT) and the intended toll response (income VOT) use **different mode-choice models** — an inconsistency a reviewer will catch.
- **Fix:** wire `apply_plans.py` income-VOT (with the toll term) into the toll outer-loop, run base *and* toll through the same income-VOT layer, and state clearly which model produces the reported elasticity. Do NOT claim "ABIT mode choice is income-elastic."

### CR-2 — The study corridor fails link validation; the "PASS" is manufactured
- I-695 — the tolled corridor the paper is about — is the worst-correlated freeway: **R²=0.17, ratio 0.53, FAIL** (`04` C2).
- `route_validation_summary_table.png` stamps **"ALL mainline PASS"** via an OR-gate that only trips the weak `R²≥0.70` disjunct, while GEH<5=6% (needs 85%), within-band=17% (needs >50%), %RMSE=100% (`04` C1). And "R²" is squared Pearson correlation over stations spanning 2+ orders of magnitude — range-inflated, blind to link accuracy.
- **Fix:** drop the OR-gate PASS. Report the honest result: the resident-only model **under-predicts freeway links by scope** (through + commercial excluded). Frame the base as *screenline/arterial-validated, freeway-scope-limited* — not "validated." This is defensible IF stated honestly.

---

## MAJOR

### MJ-1 (SILO) — Re-anchor ↔ employment circularity biases the export year
`CompositionReanchorModelMstm.swap()` clones households (clones carry **no jobs**), runs in `endYear` *after* the employment model, so `UpdateOccupationModelMstm` relabels the clones' workers non-employed (~240k swaps/yr → downward employment bias in the 2023 export). `participationScaler=1.12` (PA/WV) may be **masking** this artifact rather than fixing real under-participation. HBW trips key off EMPLOYED. **Fix:** copy jobs on clone, OR run re-anchor before the employment model, OR document the scaler as a correction for this artifact.

### MJ-2 (ABIT) — Toll mispriced onto shared modes
`AUTO[]` flags CAR_PASSENGER + SHARED_RIDE as toll-payers; the gc slopes make a toll cut carpool utility 2–3× harder than solo driving (`03` M1). Passengers don't pay road tolls; the sign is backwards for an HOV-incentive study. **Fix:** toll only the driver (or per-vehicle, split correctly), verify the slope sign.

### MJ-3 (ABIT) — Frequency inflation (5.7/5.2) justified by a fictional mechanism
Javadoc blames "~40% of tours dropped for unreachable zones," but destination choice never drops a tour (`03` M2). The real cause is the representative-day extraction discarding the Tue–Fri half (`03` M3 — `abit_day.py` claims uniform scatter but the day-assignment concentrates 50% on Monday). The inflation factors are unaudited free knobs. **Fix:** audit the day-of-week logic, derive the expansion from the actual discarded fraction, not a fictional drop.

### MJ-4 (VAE) — Overstated methods + disclosure gaps
"Constrained decoding masks" claimed but code does **post-hoc overwrites** (`README.md:15`, no logit masking) — rename to "post-hoc constraint enforcement." Structural-zeros validation is **circular** (checks what `apply_constraints` just enforced) — report the *pre-patch* illegal-combo rate instead. Couple age-gap is **2× reality** (7.55 vs 3.69 yr) — disclose as a limitation. Core VAE math (KL, reparameterization, free-bits, train/test split) is correct.

### MJ-5 (MATSim figures) — Metric labeling + figure honesty
"R²" is correlation², not coefficient of determination (hides −33% bias); selective `model=0` dropping lifts corr² 0.759→0.789; on-figure "+3% bias" is an outlier artifact (median −33%); speed figure draws a "65" line while its freeway bars sit at ~50 (trunk pooled with motorway); unsupported causal caption ("below-1:1 = through cars"); base freeways barely congest (−1.5%) yet captioned "congestion forming." **Fix:** label metrics correctly, report medians, un-pool trunk/motorway, soften causal claims to hypotheses.

---

## MINOR (representative)
- ABIT: hard-coded "RTS-derived" stop CDFs with no loader/script; WORK/EDU stop mass hard-zeroed→OTHER; teleport-to-random-zone dead code; no telework (100% 5-day commute); re-anchored ASCs so large base shares are constant-dominated.
- SILO: person totals not conserved by income/4+ swaps; income vs size passes with no joint convergence check; household race = first-listed member; occupation re-rolled yearly (person-level flicker).
- VAE: income_bin exceeds its noise floor; "reconciled exactly" is 99.98%; memorization metric conflates fidelity with copying.

---

## What's solid (credited — a fair review)
- **VAE:** correct analytic KL, reparameterization (√var), free-bits, honest train/test split, **no data leakage**.
- **SILO:** thread fix correct + complete (no pool accumulation, no race); auto-ASC math exact; per-state levers applied once (non-compounding); occupation bands gapless; re-anchor conserves household count.
- **ABIT:** ordered-logit stop math correct (normalized CDFs, WORK/EDU never drawn); two-component gravity is valid monotone LOS-sensitive impedance; softmax + toll sign correct; `build_studyarea.py` jitter is a correct uniform-in-polygon sampler with correct 26918→26985 reprojection, home coords untouched, NaN-guarded.
- **MATSim:** GEH formula correct; ×10 sample scaling applied exactly once end-to-end; station→link matching careful + conservatively biased *against* the model; calibration/held-out split honest with leak checks; `gate.json` + loglog scatter report the failures faithfully.

## Priority order for the paper
1. **CR-1** (income-VOT engine wiring + honest attribution) — the equity story depends on it.
2. **CR-2** (drop manufactured PASS; honest freeway-scope framing).
3. **MJ-1** (SILO employment bias — decouples the participation-scaler circularity).
4. **MJ-2, MJ-3** (toll-on-passengers; frequency-inflation provenance).
5. **MJ-4, MJ-5** (VAE + figure disclosure/labeling).

**Bottom line:** nothing is fabricated and the math is right, but the **claims and figures currently overstate a base model that fails standard freeway link-count criteria by design (scope)**, and the **income-elastic toll engine must be wired in and honestly attributed** before any equity result is reported.
