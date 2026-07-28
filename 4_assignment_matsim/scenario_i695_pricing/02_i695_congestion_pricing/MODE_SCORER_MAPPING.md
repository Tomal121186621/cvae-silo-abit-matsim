# Porting the Maryland mode-choice model into the MATSim scorer (for SubtourModeChoice under I-695 pricing)

Follows MATSim-NYC (paper `2008.04762v2.pdf`, Sec. 4.1.1, Eqs. 1–3, Table 2): convert our estimated
MNL mode-choice model into an equivalent MATSim utility-based scorer, **normalize the car travel-time
coefficient to 0** and rebase the others, keep it **VOT-consistent**, then **re-anchor the ASCs** so the
no-toll base reproduces our validated mode shares. Only then does the road-pricing scenario turn on the
toll and let SubtourModeChoice + ReRoute + TimeAllocationMutator find the response — **no outer loop**.

---

## 1. Source model (what we are porting)

Chayan & Cirillo (2024), estimated with Biogeme on MWCOG RTS 2017–18; the active MITO/ABIT model.
Multinomial logit, reference = CAR_DRIVER. Coefficient files:
`ABIT/input/maryland/coef/modechoice_full_*.csv`.

- **Modes (7):** CAR_DRIVER, CAR_PASSENGER, SHARED_RIDE, BUS, TRAIN, WALK, BIKE.
- **Utility:** `V_m = ASC_m + β·(socio-demographics) + β_gc,m·GC_m + β_tl,m·tripLength_m`
- **Generalized cost:** `GC = travel_time[min] + (distance × monetaryCost) / VOT` — one term combining
  time and money via the mode's VOT. **This is the crux of the port:** MATSim needs time and money as
  *separate* scorer channels so that the road-pricing toll (a pure $) is scored consistently, so we must
  **split GC back into a per-hour time coefficient and a per-$ money coefficient.**
- **VOT / cost framework** (`mode_choice_spec.md`): `VOT_autoD = VOT_autoP = 30`, `VOT_transit = 15`,
  `VOT_sharedRide = 40` ($/h); `fuelCost = 0.12/km`, `transitFare = 0.50/km`. (Euro-named in legacy code
  but these are the values the MD coefficients were estimated/applied with — internally consistent.)

### β_gc by purpose (car is `β_gc,CAR_DRIVER`)
| Purpose | CAR_DRIVER | CAR_PASS | SHARED_RIDE | BUS | TRAIN |
|---|---|---|---|---|---|
| Work (HBW) | −0.013 | −0.035 | −0.027 | −0.030 | −0.006 |
| Education | −0.013 | −0.035 | −0.027 | −0.030 | −0.006 |
| Accompany/Other/Recreation | −0.022 | −0.022 | −0.005 | −0.040 | −0.018 |
| Shopping | −0.070 | −0.080 | −0.040 | −0.150 | −0.020 |

The MATSim scorer is **global (one set of mode params for the whole day)**, but β_gc is purpose-specific.
**Resolution:** use the **trip-weighted mean β_gc across purposes** for the committed scorer, and use
**HBW as the worked example below** (commute is the movement congestion pricing targets, and dominates
the priced peak windows). WALK/BIKE carry no GC term; their disutility is the `tripLength` coefficient
(WALK −1.17, BIKE −0.28 per km for HBW).

---

## 2. The GC split (time ↔ money), VOT-consistent

For mode `m`: `β_gc,m · GC_m = β_gc,m·time[min] + (β_gc,m / VOT_m)·cost[$]`.

- **Per-hour travel-time coefficient:** `b_time,m = β_gc,m × 60` (utils/h)
- **Per-$ cost coefficient:** `b_cost,m = β_gc,m × 60 / VOT_m` (utils/$), with VOT_m in $/h.

Worked for **HBW**:

| Mode | β_gc | VOT ($/h) | b_time = β_gc×60 (utils/h) | b_cost = β_gc×60/VOT (utils/$) |
|---|---|---|---|---|
| CAR_DRIVER | −0.013 | 30 | **−0.78** | **−0.026** |
| CAR_PASSENGER | −0.035 | 30 | −2.10 | −0.070 |
| SHARED_RIDE | −0.027 | 40 | −1.62 | −0.0405 |
| BUS | −0.030 | 15 | −1.80 | −0.120 |
| TRAIN | −0.006 | 15 | −0.36 | −0.024 |

**Consistency check:** car VOT recovered = `b_time,car / b_cost,car = 0.78 / 0.026 = $30/h` ✓ = the
model's `VOT_autoD`. The **toll acts on car trips**, so this is the sensitivity that governs the
congestion-pricing response — and it is reproduced *exactly*.

### Single global `marginalUtilityOfMoney`
MATSim allows only **one** `marginalUtilityOfMoney`. RoadPricing adds the toll as negative money, scored
by this one value, so we anchor it to **car**:

> **`marginalUtilityOfMoney = 0.026` utils/$** (= |b_cost,car|).

Per-mode differences in cost sensitivity (e.g. transit riders' −0.120/$) are then absorbed into the
**ASC re-anchor** (Sec. 4) at the base — exactly as MATSim-NYC used a single `β_cost = −0.06` for all
modes and calibrated constants to shares. The toll response, which is what we report, stays car-exact.

---

## 3. MATSim scorer parameters (the `planCalcScore` / `ScoringConfigGroup` mode table)

MATSim network modes here are **`{car, pt, ride, walk, bike}`** (RunBaltimore). Our 7 modes collapse:

| Our mode(s) | MATSim mode |
|---|---|
| CAR_DRIVER | `car` |
| CAR_PASSENGER + SHARED_RIDE | `ride` (teleported) |
| BUS + TRAIN | `pt` (routed on schedule) |
| WALK | `walk` |
| BIKE | `bike` |

**Normalization (NYC recipe):** subtract car's `b_time` (−0.78/h) from every mode's travel-time
coefficient so **car = 0**, and set `marginalUtilityOfPerforming = +0.78/h` (= |b_time,car|, also serves
as β_dur per NYC). Net time cost is preserved: e.g. car net = 0 − 0.78 = −0.78/h; train net =
+0.42 − 0.78 = −0.36/h. ✓

### Table — MATSim ModeParams (HBW-based; commit trip-weighted means)

| MATSim mode | `constant` (ASC, *pre*-anchor) | `marginalUtilityOfTraveling` (utils/h, car-normalized) | `marginalUtilityOfDistance` (utils/m) | `monetaryDistanceRate` ($/m) |
|---|---|---|---|---|
| `car`  | 0.00 (reference) | **0.00** | 0 | −0.000075  (fuel ~$0.12/km) |
| `pt`   | 2.25→blend (see note) | **−1.02** (from BUS −1.80) | 0 | −0.0005  (fare $0.50/km; or 0 and fare in ASC) |
| `ride` | 3.87 (AutoP/SR blend) | **−1.11** (from −2.10/−1.62 blend) | 0 | −0.000075 (shared fuel) |
| `walk` | 3.97 (WALK) | +0.78 (net 0 time) | **−0.00117** (tripLength −1.17/km) | 0 |
| `bike` | −0.20 (BIKE) | +0.78 (net 0 time) | **−0.00028** (tripLength −0.28/km) | 0 |

Global scorer settings:
- `marginalUtilityOfMoney = 0.026`
- `performing = 0.78` (utils/h)  ·  `waiting`, `lateArrival` per Sec. 4.1.2 of the paper (β_lateArr ≈
  −2.39×|car time| if scheduling is enabled; base run leaves activity params as in RunBaltimore).
- `utilityOfLineSwitch` / `marginalUtilityOfWaitingPt` for pt transfers ≈ NYC transfer penalty (optional).

**Blend notes (calibration choices, reconciled by the ASC re-anchor):**
- `pt` collapses BUS+TRAIN. Transit is ~2% and bus-dominant, so we take **BUS** params for `pt`
  (−1.02/h normalized). A demand-weighted BUS/TRAIN average is the alternative.
- `ride` collapses CAR_PASSENGER (−1.32/h normalized) + SHARED_RIDE (−0.84/h) → ~**−1.11/h** blend.
- `constant` values above are the raw HBW ASCs as a *starting point only* — they are overwritten by the
  re-anchor. (Collapsing 7→5 modes changes the choice set, so raw ASCs will not reproduce shares until
  re-anchored.)

**Units flag:** `tripLength`/GC distance is assumed **km** (MITO convention → per-m rates above divide by
1000). If the ABIT skim feeds **miles**, divide by 1609.344 instead. Verify against the distance skim
before committing (`mode_choice_spec.md` raises the same caveat).

---

## 4. ASC re-anchor step (so the no-toll base reproduces validated shares)

Target mode shares (validated resident base): **car ≈ 76%, pt ≈ 2%**, remainder split ride/walk/bike per
the RTS/ABIT validation. Procedure (standard MATSim share calibration; mirrors our SILO auto-ASC
self-calibration):

1. **Freeze** all non-constant scorer params from Sec. 3. Hold **`car` constant = 0** (reference).
2. Enable **SubtourModeChoice** (Sec. 5) and run the **no-toll base** to a relaxed equilibrium
   (~the base iteration count).
3. Compute simulated shares `ŝ_m`. Update each non-car constant:
   `ASC_m ← ASC_m + ln(s_m^target / ŝ_m)`  (one-dimensional logit-share adjustment).
4. Repeat 2–3 (typically 3–5 outer passes) until every mode share is within tolerance (±0.5–1 pp; car
   within ±1 pp of 76%, pt within ±0.3 pp of 2%).
5. **Freeze the re-anchored ASCs.** These constants define the base. **Every I-695 pricing run then uses
   the identical frozen scorer** and differs *only* by loading `roadpricing_i695.xml` — so all mode /
   route / departure-time changes are attributable to the toll, not to re-calibration.

This is exactly NYC's logic: constants calibrated to reproduce base shares, then the policy applied on
top with the scorer held fixed.

---

## 5. Wiring SubtourModeChoice in the runner (currently modes are FIXED)

`RunBaltimore.java` today fixes modes (only ReRoute + TimeAllocationMutator + ChangeExpBeta) because the
base is a pure assignment of MITO's mode choice. The pricing scenario must let travelers switch modes:

```java
// modes MATSim may switch between
config.subtourModeChoice().setModes(new String[]{"car","pt","ride","walk","bike"});
config.subtourModeChoice().setConsiderCarAvailability(true);
config.subtourModeChoice().setBehavior(
    SubtourModeChoiceConfigGroup.Behavior.betweenAllAndFewerConstraints);
// add the replanning strategy (rebalance weights; keep innovation off for the last 20%)
addStrategy(config, "SubtourModeChoice", 0.15);   // alongside ReRoute 0.15, TimeMutator 0.10, ChangeExpBeta ~0.60
```

and populate each `ScoringConfigGroup.ModeParams` with the Sec. 3 values (currently they are added with
defaults). See Sec. 6 for the road-pricing wiring the strategy depends on.

---

## 6. Dependency: RoadPricing must also be wired (see toll deliverable)
The toll enters the scorer as money via `org.matsim.contrib.roadpricing`. That contrib is **not in the
current jar** — it must be added to `pom.xml` and the module installed in the runner (see the report /
`toll/i695_toll_schema.md`). Without it, `marginalUtilityOfMoney` has nothing to act on and the pricing
scenario is identical to the base.
