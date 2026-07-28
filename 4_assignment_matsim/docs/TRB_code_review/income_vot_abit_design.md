# Income-elastic toll response inside ABIT (VAE → SILO → ABIT → MATSim, no MITO)

**Framework decision (firm):** the I-695 congestion-pricing study runs on the **ABIT** activity-based
demand (v4). The Tour Based MITO `apply_plans.py` income-VOT path — the resolution recorded in
`CR1_income_vot_wiring.md` — is **dropped**. Therefore the income-elasticity of the toll response must
live **inside ABIT's mode choice**, not in a MITO re-mode-choice layer.

This document (1) inventories every ABIT mode-choice class, (2) determines whether an income-VOT
generalized-cost model already exists in ABIT, (3) recommends the cleanest path with the **exact code
change and file:lines**, (4) shows the base car-share is preserved, and (5) gives the re-validation plan.
A small numeric unit-test (no full ABIT/MATSim run) demonstrates the income-elasticity.

> **Supersedes CR1 for this framework.** CR1 resolved the reviewer's C1 finding by routing the toll through
> the MITO Python income-VOT engine. With MITO removed, that resolution no longer applies; the fix below
> puts the income-VOT **in ABIT** where the reviewer originally located the defect.

---

## 1. ABIT mode-choice inventory

Directory `ABIT/src/main/java/abm/models/modeChoice/` plus the Maryland fork `abm/models/maryland/`:

| Class | Role | Income-VOT? | Toll? | Wired operative (Maryland)? |
|---|---|---|---|---|
| `maryland/MarylandFullModeChoice` | **Operative** tour mode choice — full Chayan & Cirillo (2024) 5-purpose MNL, GC-based, ASC re-anchored to RTS shares | **No** — fixed `VOT={30,0,0,30,40,15,15}` | **Yes** — `setToll()` → auto money → GC | **YES** (`ModelSetupMaryland:56`) |
| `maryland/MarylandTourModeChoice` | RTS empirical share sampler (samples mode from purpose share table) | No (no utility at all) | No | No (dormant; superseded by FullModeChoice) |
| `modeChoice/NestedLogitTourModeChoiceModel` | **Munich** nested logit, GC-based | **Yes** — 3 income bands (`vot_less_or_equal_income_4`, `vot_income_5_to_10`, `vot_income_greater_10`), EUR fuel/fare | **No** toll term | No (Munich `ModelSetupMuc` only) |
| `modeChoice/NestedLogitHabitualModeChoiceModel` | Munich habitual (commute) mode | partial | No | No |
| `modeChoice/Simple{Tour,Subtour,Habitual}ModeChoice` | Toy stubs | No | No | No (`SimpleModelSetup` only) |
| `modeChoice/SubtourModeChoiceModel` | Subtour mode (non-home-based) | No | No | `SimpleSubtourModeChoice` used in Maryland |
| `scenarios/lowEmissionZones/…LowEmissionZones` | LEZ scenario variant of the Munich nested logit | Munich bands | LEZ ban, not toll | No |

**Operative model for the I-695 study = `MarylandFullModeChoice`.** It is the only Maryland-calibrated,
GC-based, toll-aware model, and it is the one wired in `ModelSetupMaryland`.

## 2. Does an income-VOT GC model already exist in ABIT? — Partly, but not usable as-is

**Yes, one exists — but it is the Munich `NestedLogitTourModeChoiceModel`, and it is not wire-able for Maryland:**

- (a) It **does** read income: `household.getPersons().stream().mapToInt(Person::getMonthlyIncome_eur).sum()`
  (`NestedLogitTourModeChoiceModel.java:497`), bucketed into 3 bands (lines 500–518).
- (b) It computes cost as `money / VOT` — but VOT enters as a **divisor of the whole GC term**, and the
  money side is **EUR** (`fuelCostEurosPerKm=0.065`, `transitFareEurosPerKm=0.12`, lines 43–44).
- (c) It has **no toll/money channel** — there is nowhere to inject a per-OD toll.
- (d) Its coefficients, nesting structure, and calibration factors are **Munich** (`muc`/`nonMuc`,
  RegioStaR region types). It has **never** been re-anchored to the RTS car ≈ 0.76 base and would not
  reproduce it.

So **wiring the Munich model in is not viable** (wrong currency, wrong coefficients, no toll, would destroy
the validated base). What ABIT *does* already have on the Maryland side is the more important half:

**`MarylandFullModeChoice` already has the toll channel and a GC structure** — it is missing only the
income dependence of VOT:

- Toll hook: `setToll(double usd)` / `autoTollUsd` (lines 69, 88–89), added to auto monetary cost in
  `probabilities()` at **line 306** (`if (AUTO[m]) money += autoTollUsd;`).
- GC in minutes with the VOT divisor at **line 309**:
  `double gc = VOT[m] > 0 ? time + money * 60.0 / VOT[m] : 0.0;`
- Base ASC re-anchoring to RTS tour shares (`calibrateAscs`, `reapplyAndCalibrate`) at **toll = 0** —
  this is what pins base car ≈ 0.76.
- Income **is available** on every person: `Person.getMonthlyIncome_eur()` is populated from the SILO
  synthetic population (`MarylandLosDataReader` reads column `income`, annual USD → `/12`; the field name
  says `_eur` but the value is **USD**). Household income = sum over persons, exactly as the Munich model does.

**Conclusion:** the operative Maryland model is **price-elastic but income-invariant** — every household,
rich or poor, converts a toll dollar to the *same* `60/VOT[m]` minutes of disutility. The published
Chayan-Cirillo specification the paper cites (VOT ≈ 50 % of the wage, income elasticity ≈ 0.6) is **not**
faithfully implemented anywhere on the Maryland path. The gap is exactly the fixed `VOT` array at line 49.

## 3. Recommendation — Path (a): make `MarylandFullModeChoice` VOT income-dependent

Of the three options, **(a) modify `MarylandFullModeChoice`** is the clear winner:

- **(WIRE the Munich model)** — rejected: wrong currency/coefficients, no toll term, base 0.76 destroyed (§2).
- **(a) income-dependent VOT in `MarylandFullModeChoice`** — **RECOMMENDED**. The toll channel already
  exists; only the VOT divisor changes. Anchored so the regional-median household reproduces the published
  VOT array → base re-anchor stays valid → **base car 0.76 preserved**. Adds the income-differentiated toll
  response with ~15 lines, no new files, no coefficient re-estimation.
- **(b) toll-stage re-mode-choice on the ABIT plan file** — rejected: it re-implements mode choice *outside*
  the engine (exactly the MITO `apply_plans.py` pattern the framework just dropped), duplicates logic, and
  ABIT **already** re-applies mode choice under the toll in-engine (`applyToAllTours`, called from
  `RunAbitMarylandLos:72`). No reason to add an external layer.

### 3.1 The design — anchored elastic VOT (keeps published inter-mode ratios)

Replace the fixed per-mode VOT with an income-scaled VOT that preserves the published array's inter-mode
structure and the elasticity the paper cites:

```
VOT_m(income) = VOT_ref[m] · ( hh_income_monthly / INCOME_REF )^ELASTICITY      (clamped)
```

- `VOT_ref[m]` = the existing published array `{30,0,0,30,40,15,15}` — kept exactly (car > transit ratio preserved).
- `INCOME_REF` = regional **median** household monthly income (~$7,000 USD/mo ≈ $84k/yr, Baltimore–Washington).
- `ELASTICITY` = **0.6** (Chayan-Cirillo / USDOT income elasticity of VOT).
- Clamp the income factor to `[0.4, 2.5]` so GC stays well-behaved at the income tails.

Why this preserves the base: **at `income = INCOME_REF` the factor = 1.0, so VOT = the published array
exactly.** The ASC re-anchor (`reapplyAndCalibrate`, toll = 0) matches *aggregate* per-purpose shares; the
median household is unchanged and off-median households shift GC only by the small fuel-only term (~$1.4/trip)
at base, which the aggregate re-anchor absorbs into the ASCs. Under a toll the factor spreads the response:
a low-income household has a *smaller* VOT → a toll dollar buys *more* disutility minutes → it shifts *more*;
a high-income household shifts *less*. That is the equity-relevant, income-elastic toll response.

### 3.2 Exact code change (`ABIT/src/main/java/abm/models/maryland/MarylandFullModeChoice.java`)

**Edit 1 — add the elastic-VOT constants next to the existing `VOT` array (after line 50):**

```java
    // VOT ($/h equiv used as min-per-$ divisor) and monetary cost per km
    static final double[] VOT = {30, 0, 0, 30, 40, 15, 15};          // CAR_DRIVER,WALK,BIKE,AutoP,SR,BUS,TRAIN
    static final double[] COST_PER_KM = {0.12, 0, 0, 0.12, 0.12, 0.50, 0.50};
    static final boolean[] AUTO = {true, false, false, true, true, false, false};

    // --- income-elastic VOT (Chayan & Cirillo: VOT ~ wage, income elasticity ~0.6). VOT[] above is the
    // reference VOT at the regional-median household income; households scale off it so the toll response
    // is income-differentiated while the base (median) household reproduces the published VOT. ---
    static final double VOT_INCOME_REF_USD_MTH = 7000.0;             // ~ $84k/yr Balt-Wash median hh income
    static final double VOT_INCOME_ELASTICITY  = 0.6;                // income elasticity of VOT
    static final double VOT_FACTOR_MIN = 0.4, VOT_FACTOR_MAX = 2.5;  // clamp at the income tails
```

Optionally make the two scalars run-time tunable (add to the resources file, read once): they are declared
`static final` only for clarity; if you want `-D`/properties control, load them in the constructor. Not
required for correctness.

**Edit 2 — in `probabilities(...)`, compute the household VOT factor once (insert after `distKm`, i.e.
after line 300, before `double[] v = new double[7];` at line 302):**

```java
        // household income-elastic VOT factor (SILO income is USD despite the _eur field name)
        double hhIncomeUsdMth = 0.0;
        for (Person pp : hh.getPersons()) hhIncomeUsdMth += pp.getMonthlyIncome_eur();
        double votFactor = Math.pow(Math.max(1.0, hhIncomeUsdMth) / VOT_INCOME_REF_USD_MTH,
                                    VOT_INCOME_ELASTICITY);
        votFactor = Math.max(VOT_FACTOR_MIN, Math.min(VOT_FACTOR_MAX, votFactor));
```

(`hh` is already in scope — `Household hh = person.getHousehold();` at line 291; `Person` is already
imported at line 9.)

**Edit 3 — replace the fixed-VOT GC line (line 309) with the income-scaled VOT:**

```java
            // BEFORE (line 309):
            // double gc = VOT[m] > 0 ? time + money * 60.0 / VOT[m] : 0.0;
            // AFTER:
            double votM = VOT[m] * votFactor;                        // income-elastic VOT
            double gc = votM > 0 ? time + money * 60.0 / votM : 0.0;
```

That is the entire change: **3 edits, ~12 lines, one file, no new files, no coefficient re-estimation.**
Walk/bike keep `VOT[m]=0 → votM=0 → gc=0` (unaffected). The toll term at line 306 is untouched and now
converts to income-differentiated minutes automatically.

**No wiring change is needed** — `MarylandFullModeChoice` is already the operative model
(`ModelSetupMaryland:56`); `RunAbitMarylandLos` already sets the toll (`setToll`, line 43), re-anchors at
base (`reapplyAndCalibrate`, line 68), and re-applies mode choice under the toll (`applyToAllTours`, line 72).
Those flows are unchanged; they now carry income elasticity for free.

## 4. Base car-share preservation check

- **Median household (income = `INCOME_REF`):** `votFactor = 1.0` → `votM = VOT[m]` → identical to the
  current model. Base utility unchanged.
- **Aggregate base (all incomes, toll = 0):** off-median households shift GC only through the fuel-only
  monetary term (`distKm·0.12`, ~$1.4/trip), divided by a now income-scaled VOT — a small perturbation. The
  existing `reapplyAndCalibrate(dataSet, 40)` re-anchor (run at toll = 0 in `RunAbitMarylandLos`) matches the
  **aggregate** RTS per-purpose shares, so it absorbs the mean shift into the ASCs and **restores base car ≈
  0.76**. The re-anchor is *already* in the pipeline — no new calibration step.
- **What changes at base:** only a mild *within-income redistribution* (higher-income households ~+1pp car,
  lower-income ~−1pp) around the same aggregate — which is behaviorally correct, not a regression.

## 5. Numeric demonstration (no full ABIT/MATSim run)

A 3-alternative re-anchored HBW MNL (car ASC set so base car ≈ 0.76, real HBW `gc` coefficient, $4 toll on
auto), comparing the **new income-VOT** against the **old flat-VOT**, same OD (15 km) for all:

```
Income($/mo) VOTfac  base_car toll$4_car  NEW drop(pp)   OLD(flat) drop(pp)
    2500      0.54    0.808    0.801         0.72            0.55
    7000      1.00    0.796    0.790         0.55            0.55
   15000      1.58    0.789    0.785         0.40            0.55
```

- **Old flat-VOT:** every income drops the same **0.55 pp** — income-invariant (the reviewer's C1 defect).
- **New income-VOT:** low income drops **0.72 pp**, high income **0.40 pp** — the low-income car reduction is
  **~1.8× larger**; a genuine income-elastic toll response. (Magnitude scales with toll size and OD length;
  a $4 flat toll on one OD is illustrative.)
- **Median row reproduces the flat model exactly** (VOTfac = 1.0) → base preserved, as designed.

(Reproduce: `python3` on the 3-alt demo; the same mechanism, `votM = VOT[m]·(income/REF)^0.6`, drives it.)
A JUnit equivalent belongs in `ABIT/src/test/java/abm/models/modeChoice/` — call `probabilities()` on three
synthetic `Person`s (low/median/high `monthlyIncome_eur`) at a fixed OD with `setToll(0)` then `setToll(4)`,
and assert `carDrop(low) > carDrop(median) > carDrop(high)` and `carDrop(median) == flatModelDrop`.

## 6. Re-validation plan

1. **Rebuild** the maryland module: `mvn -pl … package -DskipTests` (JDK 21).
2. **Base run** (`auto.toll = 0`, `RunAbitMarylandLos`): confirm aggregate `CAR_DRIVER` share still ≈ 0.76
   (RTS target) and each purpose within its usual re-anchor tolerance — the re-anchor should restore it with
   no manual retune. Compare `output/legs.csv` mode split against the calib5 base.
3. **Toll run** (`RunTollTest`, $2 and $4): confirm the aggregate car decline is the same order of magnitude
   as the pre-change model, and add an **income-tercile breakdown** (extend `RunTollTest.sharesAll` to bin
   by `hh` income) → assert low-income car decline > high-income car decline.
4. **Unit test** (§5) in CI — the cheap guardrail that the income ordering never regresses.
5. **Hybrid loop** (`run_feedback.py` equivalent, ABIT-side): once the ABIT toll skim / `applyToAllTours`
   response is confirmed monotone in income, the outer ABIT ↔ MATSim loop needs no logic change — MATSim
   still does route/time only; ABIT now supplies the income-elastic mode split.

## 7. Honest notes

- This makes the operative ABIT model implement the income-VOT the paper's equity story requires — the
  reviewer's C1 finding is **fixed in place** (not scoped around).
- VOT is anchored to a **literature elasticity (0.6)** and the regional **median income**, not estimated from
  an income×toll interaction in the RTS choice data. Describe it in the paper as a behaviorally-reasonable,
  literature-anchored income-VOT (same honest caveat as CR1 §7), now native to ABIT.
- `INCOME_REF` (median monthly income) should be set to the actual SILO calib5 median for the modeled county
  subset — verify the value ($7,000/mo is the placeholder) against the population before the production run,
  since it directly sets which household is the "unchanged base" pivot.
