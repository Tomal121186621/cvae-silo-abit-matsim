# CR-1 resolution — wiring the income-elastic toll response into the operative pipeline

**Finding (reviewer C1, `03_ABIT_MITO_review.md`):** the "income-elastic toll response" the paper's
equity story depends on does not exist in `ABIT/…/MarylandFullModeChoice.java` — VOT there is a hard-coded
per-mode constant array `{30,0,0,30,40,15,15}` and no household/person income is read, so every driver
converts a toll to the same generalized-cost minutes and the toll response is income-invariant.

**Resolution:** the operative I-695 congestion-pricing pipeline does **not** run the ABIT Java
`MarylandFullModeChoice`. It runs the **Tour Based MITO** engine, whose mode choice
(`apply_plans.apply_mode`) is a genuine **income-VOT MNL**. This document records the operative toll-loop
architecture, confirms the income-VOT layer is wired for both base and pricing runs, states the one wiring
guard added, and gives the unit-test evidence of an income-differentiated toll response.

---

## 1. Two mode-choice engines — which one is operative

| | ABIT Java `MarylandFullModeChoice` | Tour Based MITO `apply_plans.apply_mode` |
|---|---|---|
| VOT | fixed array (no income) — **C1 target** | `vot_from_income(hh_income, purpose)` (USDOT 50%-of-income, elasticity 0.6) |
| Toll term | full toll on driver **and** passenger/SR (reviewer M1 bug) | full on `autoD`, **half** on `autoP`/`sr` (M1 already avoided) |
| In the operative loop? | **No** (legacy / MATSim-scorer port, abandoned) | **Yes** — called by `run_feedback.py` |

The MATSim-scorer port (`MODE_SCORER_MAPPING.md`, SubtourModeChoice, "no outer loop") was **abandoned**
because the scorer couldn't reproduce ABIT's base car share (see memory `i695-toll-hybrid-approach`). The
project moved to a **hybrid outer loop** — and that loop uses the Python income-VOT engine, not ABIT. So
C1 is a real defect in a **non-operative** code path; the operative path already carries income-VOT.

## 2. Operative toll loop (hybrid ABIT-side mode choice ↔ MATSim route/time)

`Updated MATSim/code/run_feedback.py`, per outer iteration *k*:

1. **demand** — `python3 apply_plans.py full <flow>` with `TBM_SKIM_DIR=SKDIR`. Reads the current
   congested auto skim **and** `SKDIR/toll_auto.omx` if present → income-VOT mode choice → plans.
2. **assignment** — `RunBaltimoreToll` (MATSim + RoadPricing, **fixed modes**): route + departure-time
   inner loop on the tolled network → `output_events.xml.gz` (with `personMoney` toll events).
3. **skims** — `skim_from_events.py` → congested time skim (MSA-blended back into `SKDIR`);
   `toll_from_events.py` → `SKDIR/toll_auto.omx` = per-OD trip-timing-weighted **$/car-trip**.
4. next iteration's `apply_plans` reads that toll skim → **the mode choice responds to the toll**.

So the money side of the toll (RoadPricing → `personMoney` events → `toll_from_events.py` → `toll_auto.omx`)
feeds straight into the income-VOT mode choice. Mode-shift elasticity is produced **entirely** by
`apply_mode`; MATSim only re-routes/re-times the resulting demand (modes fixed inside MATSim).

## 3. The income-VOT + toll term (already in `apply_plans.apply_mode`, lines ~347–353)

```python
vot = [vot_from_income(inc, p) for inc, p in zip(P.hh_income, T.purpose)]   # $/h, scales with income
bt  = -0.025                                    # utils/min (time)
bc  = bt / (vot/60)                             # utils/$  — LOW income -> LOW VOT -> MORE-negative bc
tollOD = S(tollM, oz, dz)                        # per-OD toll $ (0 when no toll skim -> base is a no-op)
cost["autoD"] = mi*0.20 + tollOD                 # full toll on the driver
cost["autoP"] = mi*0.10 + 0.5*tollOD             # half on car-passenger  (fixes reviewer M1)
cost["sr"]    = 2.5 + mi*1.75 + 0.5*tollOD       # half on shared-ride    (fixes reviewer M1)
# ... V_m = ... + bc*cost[m]  -> toll disutility = bc*toll, and |bc| is larger for low income
```

`apply_plans.main` (lines ~107–116, 215) loads `toll_auto.omx` from the skim dir into `tollM` and passes
it to `apply_mode`; absent → zero matrix (base unchanged). **Base and pricing runs call the identical
`apply_mode`** — the toll is the only difference, so the elasticity is internally consistent (this is what
C1 asked for, and what the fixed-VOT ABIT path could not provide).

## 4. Attribute check — can it run on the operative demand?

`apply_plans` does not consume ABIT plan CSVs; it **regenerates** tour demand from the SILO/VAE synthetic
population via `apply_io.load_population`, which supplies every covariate `apply_mode` reads:
`hh_income`, `autos`, `zerocar`, `center`, `senior`, `female`, `hhsize`, `home_zone`, `work_zone`,
`purpose`. Attribute check: **PASS** (verified in `apply_io.py:44–113`).

## 5. Wiring change made (minimal, guarded)

The plumbing (loop → toll skim → `apply_mode(tollM)`) was already present. One robustness gap was closed:

- **`Updated MATSim/code/run_feedback.py`** (seed block, after copying the base auto skim): when
  `TOLL == "NONE"` (a base loop), delete any stale `SKDIR/toll_auto.omx` left by a prior pricing run, so
  the base can never inherit a phantom toll. Guarantees base and pricing differ **only** by the toll —
  the consistency the equity comparison requires.

No change was needed in `apply_plans.py` (toll wiring already correct, including the M1-safe half-toll on
passenger/shared-ride).

## 6. Unit-test evidence (no MATSim, no full run)

`Tour Based MITO/code/apply/test_toll_income_vot.py` drives the real `apply_mode` on 1000 synthetic HBW
commuters over one 10-mile OD, base vs a flat **$4** toll, holding random draws / skims / coefficients
fixed (same seed) so the toll is the only change:

```
income-VOT (HBW): low $25,000 -> VOT $11.3/h | high $150,000 -> VOT $33.0/h
 low income  autoD: 92.0% -> 88.1%  (-3.9pp)   auto-any: 97.0% -> 93.5%  (-3.5pp)
high income  autoD: 90.5% -> 89.6%  (-0.9pp)   auto-any: 96.9% -> 96.5%  (-0.4pp)
(a) engine ran on SILO/ABIT-style attributes .......... PASS
(b) toll reduces auto-driver share (both groups) ...... PASS  (low -3.9pp, high -0.9pp)
(c) low-income shift > high-income (income-elastic) .... PASS  (low -3.9pp vs high -0.9pp; ratio 4.33x)
```

The low-income auto-driver reduction is **4.3× larger** than high-income — a genuine income-elastic toll
response, driven by `bc = bt/(vot/60)` growing in magnitude as income (hence VOT) falls.

## 7. Honest attribution

- The toll **mode-shift elasticity is produced by `apply_plans.apply_mode`** (Tour Based MITO income-VOT
  MNL), **not** by ABIT `MarylandFullModeChoice` and **not** by the MATSim scorer. MATSim/RoadPricing
  supplies the per-OD toll $ (via `personMoney` events → `toll_from_events.py`) and handles route +
  departure-time only.
- VOT is USDOT 50%-of-income anchored at the $81k regional median, sub-linear (elasticity 0.6), purpose-
  multiplied, floored/capped $6–$45/h (`rts_common.vot_from_income`). It is a **behaviorally reasonable,
  literature-anchored** income-VOT, not an estimated income×toll interaction from the RTS choice data —
  the paper should describe it as such.
- **The reviewer's C1/M1 remain true statements about `MarylandFullModeChoice.java`.** They are resolved
  for the paper by the operative pipeline running the income-VOT engine instead; the recommended paper
  edit is to (i) state the toll response comes from the Tour Based MITO income-VOT mode choice in the
  hybrid loop, and (ii) either fix or explicitly scope-out the ABIT Java model as non-operative for the
  pricing results.
```
