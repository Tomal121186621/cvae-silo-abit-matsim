# TRB Peer Review — ABIT Activity-Based Model (congestion-pricing paper)

Scope reviewed: `ABIT/src/main/java/abm/models/maryland/{MarylandFullModeChoice,MarylandDestinationChoice,MarylandStopModel,MarylandFrequencyGenerator,MarylandSplitByType,MarylandDayOfWeek*Assignment}.java`, `models/{ModelSetupMaryland,PlanGenerator}.java`, `RunAbitMarylandLos.java`, `RunTollTest.java`, `validation/{build_studyarea,abit_day}.py`, and the driving input CSVs under `input/maryland/coef/`. MITO was explicitly out of scope for this pass.

Verdict: the mechanical math (ordered-logit stops, gravity friction, softmax mode choice, polygon jitter) is largely **correct**. The problems are in the **pricing/equity representation** and in **comments/claims that do not match the code**. One CRITICAL issue undercuts the paper's central equity story.

---

## CRITICAL

### C1. No income-dependent VOT — the "income-elastic toll response" does not exist in the code
**File:** `models/maryland/MarylandFullModeChoice.java:49, 305-313` (and the entire `probabilities()` method).
**Problem:** VOT is a hard-coded per-mode constant array `VOT = {30,0,0,30,40,15,15}`. Generalized cost is `gc = time + money*60/VOT[m]` (line 309), and the toll enters through `money += autoTollUsd` (line 306). Nowhere in `probabilities()` is household or person income read — the covariate list is age, male, license, hhsize, hhautos, coreCity, medCity, rural, gc, tripLength (lines 310-313). `grep -in income MarylandFullModeChoice.java` returns only comments.
**Why it's wrong:** The project notes (`i695-toll-hybrid-approach`) state the design gives an "income-elastic toll response for free" via income-derived VOT. It does not. Every driver, rich or poor, converts a $2 toll to exactly `2*60/30 = 4` minutes of GC and receives the same disutility `b_gc·4`. There is zero income heterogeneity in the toll response. Any distributional / equity conclusion about who bears the I-695 toll is therefore **unsupported by the model** — the only cross-sectional variation in toll response comes from `hhautos`/`hhsize`/urban ASCs, none of which scale the toll by ability-to-pay.
**Fix:** Make VOT a function of person/household income (e.g., `VOT_i = base * (income_i / median)^θ`) inside `probabilities()`, or add an income×gc interaction term. Until then, drop all income-equity claims from the paper, or state explicitly that toll disutility is income-invariant.

---

## MAJOR

### M1. Toll is charged to CAR_PASSENGER and SHARED_RIDE, and suppresses carpooling *more* than solo driving
**File:** `MarylandFullModeChoice.java:50-51, 306`; coefficient `gc` row of `input/maryland/coef/modechoice_published_HBW.csv`.
**Problem:** `AUTO = {true,false,false,true,true,false,false}` flags CAR_DRIVER **and** CAR_PASSENGER **and** SHARED_RIDE as toll-paying, so line 306 adds the full toll to all three. The published `gc` slopes are CAR_DRIVER −0.013, CAR_PASSENGER −0.035, SHARED_RIDE −0.027. A $2 toll therefore changes utility by:
- CAR_DRIVER: −0.013 × (2·60/30) = **−0.052**
- CAR_PASSENGER: −0.035 × (2·60/30) = **−0.140**
- SHARED_RIDE: −0.027 × (2·60/40) = **−0.081**
**Why it's wrong:** (a) A car *passenger* does not personally pay the road toll — the driver does — so charging the full toll to the passenger alternative is a modeling error. (b) Because the passenger/shared-ride `gc` coefficients are 2–3× the drive-alone coefficient, the toll pushes travelers **out of carpooling faster than out of driving alone**. That is the opposite of the HOV incentive a congestion charge is supposed to create; a pricing paper that reports mode shifts will show shared modes collapsing under the toll for the wrong reason.
**Fix:** Charge the toll only to CAR_DRIVER (set `AUTO` true for index 0 only), or split it across occupants for SHARED_RIDE. Re-examine the perverse sign of the passenger cross-elasticity before reporting any toll mode-shift results.

### M2. Frequency inflation factors (5.7 / 5.2) are justified by a mechanism that does not exist
**File:** `MarylandFrequencyGenerator.java:52-61, 98` vs `MarylandDestinationChoice.java:122, 146-153`.
**Problem:** Discretionary weekly rate = `baseRate × discFactor`, with `F_SHOP=5.7`, `F_OTHER=5.2`. The javadoc (lines 52-54) says these factors "absorb … (b) the ~40% of discretionary tours dropped by destination choice for unreachable zones." But `MarylandDestinationChoice` **never drops a tour for an unreachable zone**: line 122 caps bad/oversized times at 600 min and still assigns them a (small) friction weight, and `selectMainActivityDestination` (146-153) always returns a zone — `total<=0` falls back to a uniform random zone, it does not drop. There is no 40%-attrition path in destination choice.
**Why it's wrong:** The 5.7/5.2 multipliers are free calibration knobs dressed up with an incorrect mechanistic story. The real attrition is the single-day extraction discarding non-Monday tours (see M3), not destination choice. Because the stated mechanism is fictional, the factors will not transfer if the population or skims change, and a reviewer cannot audit them.
**Fix:** Remove the false "destination choice drops 40%" justification. Document the factors for what they are — an empirical scale that offsets the single-representative-day extraction loss — and show the RTS daily tour-rate match that actually pins them.

### M3. Representative-day logic contradicts its own justification and silently discards ~half the discretionary tours
**File:** `validation/abit_day.py:40-47` vs `models/maryland/MarylandDayOfWeekDiscretionaryAssignment.java:35-45`.
**Problem:** `pick_day` (abit_day.py) always returns the **earliest complete weekday** = Monday for any worker (Monday carries the every-weekday work tour, so it is a complete home→work→home chain). Its docstring justifies "earliest weekday is unbiased" by asserting the engine "scatters discretionary tours across the weekdays … so **any single weekday reproduces the RTS daily distribution**." But the discretionary assignment does the opposite: `P_MON = 0.5` puts **50%** of discretionary tours on Monday and splits the other 50% across Tue–Fri (12.5% each). Monday is ~4× heavier than any other weekday, and the extractor deterministically picks Monday. So "any single weekday" is false — only Monday is representative, and the 50% of a worker's discretionary tours placed on Tue–Fri are **thrown away** by `single_day_legs`.
**Why it's wrong:** (1) The two files' stated rationales are mutually inconsistent (uniform scatter vs. deliberate Monday concentration). (2) The design is circular: discretionary tours are piled on Monday *because* pick_day picks Monday, and pick_day is "unbiased" *because* tours are supposedly uniform — neither statement is true. (3) It is fragile: change `P_MON`, or change pick_day to "busiest"/"random weekday", and the daily rate silently doubles or halves. (4) This discard is the true source of the M2 inflation factors.
**Fix:** Make the story consistent — either genuinely uniform-scatter discretionary over Mon–Fri and let pick_day take any weekday (then the factor ≈ number of weekdays, not 5.7), or keep Monday-concentration but rewrite both docstrings to state that Monday is *the* representative day by construction and that Tue–Fri discretionary tours are intentionally discarded. Report the sensitivity of headline tour rates to `P_MON`.

---

## MINOR

### m1. Stop-purpose split CDFs are hard-coded magic constants asserted to be "RTS-derived / verified"
**File:** `MarylandStopModel.java:44-69.`
The four `putStopDist(...)` rows are literals in Java with **no loader and no derivation script in the ABIT tree** (unlike `stopfreq.coefs`/`offsets`, which are read from files). The comment claims they were "derived from rts_trips_clean.csv … weighted by wttrdfin" and that the 0.60 SHOP dampening "lands SHOP at 0.166 (verified in the v4 full-MSTM run)." None of this is reproducible or falsifiable from the code under review; it is an inline assertion about a specific past run. The `0.60` dampening is a single-run tuning applied by **relabeling** SHOP→OTHER in the CDF — it does not reduce the number of stops generated (that is the frequency model), only their labels, so it will not generalize if the underlying stop over-generation changes. *Positive note:* the CDF math itself is correct — each row sums to 1.0 (HBW 0.0922+0.0641+0.1893+0.6544=1.0, etc.), `drawStopPurpose` (79-85) does a proper normalized cumulative draw, and the WORK/EDU entries of 0.0 mean those purposes are never sampled.
**Fix:** Load the split from a CSV produced by a checked-in RTS derivation script, or at minimum keep the raw RTS split and the 0.60 factor as separately-documented inputs with the run/date that produced "0.166."

### m2. WORK / EDUCATION stop mass hard-zeroed and folded into OTHER → mid-tour work/education stops mislabeled
**File:** `MarylandStopModel.java:60-69.`
Forcing HBW WORK=0 and folding the raw work/education stop mass into OTHER means the model can never emit a work- or education-purpose intermediate stop; a genuine mid-commute work errand becomes an OTHER activity. Downstream this is mostly cosmetic (stops are rubber-banded to the main-activity zone at line 200, and `build_studyarea.py` ACTMAP folds EDUCATION/RECREATION/ACCOMPANY→"other" anyway), but MATSim scores "other" with different typical duration/timing than "work." Defensible as a double-count guard given a work tour exists every weekday, but it is a modeling choice that should be stated, not buried in a comment.

### m3. `MarylandDestinationChoice.selectStopDestination` teleports to a uniform-random zone, contradicting its comment
**File:** `MarylandDestinationChoice.java:157-161.`
The comment says "stop near an attraction-weighted zone (short detour)," but the body is `int sel = rnd.nextInt(zones.size())` — a uniform random zone over the entire 6-state region, with no attraction weighting and no proximity to the tour. This is **dead in the Maryland pipeline** (with `MarylandSplitByType` every discretionary activity is PRIMARY, so `PlanGenerator`'s stop branches never fire, and real stops come from `MarylandStopModel` which rubber-bands to the main zone). But it is a latent teleport bug if this `DestinationChoice` is ever wired to a plan generator that calls `selectStopDestination`. Either implement the attraction-weighted short detour or throw `UnsupportedOperationException`.

### m4. Dead / mismatched frequency inputs
**File:** `MarylandFrequencyGenerator.java:28, 84-92`; `input/maryland/coef/rt_freq_rates.csv`.
WORK returns a fixed `WORK_DAYS_PER_WEEK=5` and EDUCATION returns 0, so the `WORK,0.2451` and `EDUCATION,0.0` rows in `rt_freq_rates.csv` are **never used** — only SHOP/OTHER/REC/ACCOMPANY read `baseRate`. Separately, the javadoc quotes "RTS daily … WORK 0.54 / SHOP 0.27 / OTHER 0.56 tours per traveler-day," which matches neither the file's rates (WORK 0.2451, SHOP 0.1347, OTHER 0.1045) nor any used quantity. Clean up the dead rows and reconcile the javadoc numbers with the actual file.

### m5. Arc-elasticity uses a hard-coded base auto cost, not the model's own trip costs
**File:** `RunTollTest.java:75, 93-98.`
The reported CAR_DRIVER arc elasticity divides the demand change by a price change built from `toll.base.autocost` (default **$1.4/trip**), an assumed constant, not the actual per-trip operating cost the model uses (`distKm·0.12`, ≈ $0.4–$1.0 for typical trips). The elasticity headline therefore scales with an arbitrary input. Compute the realized mean per-trip auto cost from the generated tours and use that as the base price, or report the elasticity's sensitivity to the assumed base cost.

### m6. 100% five-day commuting — no part-time or telework
**File:** `MarylandFrequencyGenerator.java:47, 90-92.`
Every EMPLOYED person gets a work tour on all five weekdays. For a 2023 base year in a post-COVID congestion-pricing study this overstates commute frequency and thus peak auto volumes (and the toll's revenue/diversion base). Consider a telework/part-time thinning of `WORK_DAYS_PER_WEEK`.

### m7. Re-anchored ASCs are very large — base shares are constant-dominated
**File:** `input/maryland/coef/modechoice_full_work.csv` (HBW re-anchored ASCs: WALK 8.26, BUS 6.82, vs published 3.97 / 2.25).
The "full published Chayan & Cirillo (2024)" provenance holds for the *slopes* (which drive the toll elasticity), but the base **shares** are produced by heavily re-anchored constants absorbing the transfer error between the estimation context and the Maryland synthetic population. Not a bug, but the paper should not overstate that base mode shares are "the published model" — they are the published slopes plus large local ASC corrections.

---

## What's solid (verified, not just read)

- **Ordered-logit stop frequency:** `stopfreq_coefs.csv` has `tau_1 < tau_2` in every purpose×half row; `draw()` (188-192) forms `cdf0=Λ(τ1−(v+d))`, `cdf1=Λ(τ2−(v+d))` and samples 0/1/2 correctly. Stop-purpose CDFs are normalized and WORK/EDU are correctly never drawn.
- **Gravity destination choice:** the two-component friction `f=(t+1)^b1·e^{b2·t}+w2·(t+1)^p2·e^{b3·t}` is a valid positive impedance and is **LOS-sensitive** — numerically it is monotone-decreasing for all realistic times (peaks near t≈1.2 min for the OTHER spec, then decays; e.g. OTHER f(2)=2.08, f(5)=0.65, f(10)=0.073), so a congested/tolled skim does pull destinations closer. Sampling is a correct attraction×friction inverse-CDF via binary search (149-152); unreachable times are capped, never NaN/zero.
- **Mode-choice utility algebra:** max-shift softmax (315-321) is numerically safe; GC is dimensionally consistent (minutes + $·60/VOT); published `gc` and walk/bike `tripLength` slopes are negative; the toll is plumbed into the auto monetary term with the correct demand-reducing sign. (Walk/bike GC=0 is intentional and consistent — their published `gc` coefficient is 0 and impedance is carried by `tripLength`.)
- **Intra-zonal jitter (`build_studyarea.py:100-128`):** correct rejection sampling — points are drawn in the polygon's native-CRS (EPSG:26918) bounding box, tested with `prepared.contains()` in the *same* CRS, and only the accepted point is reprojected 26918→26985; it can never place an activity outside the zone polygon; home coordinates are left untouched (`if acttype=="home": return x,y`); NaN/degenerate-sliver cases fall back to the centroid; `_random.seed(20260707)` makes it reproducible. CRS direction and order are correct.
- **Commute guaranteed on the representative day:** `WORK_DAYS_PER_WEEK=5` plus the weekday-heavy mandatory day assignment (`MarylandDayOfWeekMandatoryAssignment`) correctly ensures Monday carries a work tour for employed persons.

## Bottom line
The engine's arithmetic is sound and the jitter fix is correct. The paper-critical defects are **C1 (no income-VOT, so no basis for toll equity claims)** and **M1 (toll mispriced onto passenger/shared modes, producing a backwards carpool response)**; both must be fixed or scoped-out before any distributional or mode-shift result from the toll scenario is reported. **M2/M3** show the tour-generation calibration rests on a fictional mechanism and a self-contradictory representative-day rule — the numbers may match RTS, but the stated reasons are wrong and fragile.
