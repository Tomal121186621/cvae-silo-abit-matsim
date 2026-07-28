# TRB peer review — MATSim assignment, validation code, and publication figures

Scope audited (all under `Updated MATSim/`):
`code/matsim-run/.../RunBaltimoreToll.java`, `code/netval2023_common.py`,
`code/validate_base_hybrid.py`, `code/select_resident_targets_2023.py`,
`code/robust_match_aadt_2023.py`, `code/make_netval2023_figures.py`,
`code/make_nyc_style_figures.py`, `code/speed_audit.py`, and the outputs in
`network_validation_2023/FINAL_FIGURES/{aadt_validation_by_route, network_audit, speed_audit}/`
plus `ABIT/validation/rts_tripgen_dist/`.

Verdict: the **raw metrics are computed correctly and the model's weaknesses are
recorded honestly in the CSVs / gate.json** (GATE_PASS=false, −44% freeway bias,
6% GEH<5 are all written down). The problems are in the **PASS/verdict layer and a
few figure captions**, which reframe a model that fails the standard link-count
criteria as "validated." A strict reviewer will not accept the headline PASS.

---

## CRITICAL

### C1. "ALL (mainline) PASS" is manufactured by an OR-gate on the one metric that range-inflation favours
**Where:** `FINAL_FIGURES/aadt_validation_by_route/route_validation_summary_table.png`
(and `route_validation_summary.csv`), footnote: *"PASS = GEH<5≥85% OR within-band
majority OR R²≥0.70."*

**Problem:** The ALL-mainline row is stamped **PASS** while, on the same row:
- %RMSE = **100%**
- GEH<5 = **6%** (FHWA wants ≥85%)
- within-facility-band = **17%** (a "majority" gate wants >50%)
- median ratio = **0.72** (−28%)

It passes **only** through the `R²≥0.70` disjunct (R²=0.77). Two of the three
disjuncts fail catastrophically (6% vs 85%; 17% vs 50%) and the OR lets the single
most lenient one carry the verdict. Worse, that lenient metric is squared Pearson
correlation over a **pooled sample of 2,108 stations spanning collectors → freeways
(2+ orders of magnitude in AADT)**. Cross-facility magnitude spread mechanically
inflates correlation regardless of link-level accuracy — the co-located GEH (6%) and
%RMSE (100%) are the metrics that actually measure accuracy, and both fail. Every
individual freeway route in the table FAILS except I-83/I-70/MD-295.

**Why wrong:** Presenting a model that meets 0 of 3 FHWA/NCHRP link-count criteria
(GEH, %RMSE, band coverage) as "PASS" via a range-inflated pooled r² is metric
cherry-picking. TRB reviewers read the GEH<5=6% next to the PASS and reject the table.

**Fix:** Report the verdict as FAIL against standard link criteria and re-frame under
the resident-only scope explicitly (as the markdown body already does), OR require
ALL three criteria (AND, not OR). Do not let pooled r² override GEH/%RMSE.

### C2. The study corridor (I-695) has R²=0.17 and FAILS — the paper is about tolling I-695
**Where:** `route_validation_summary.csv` / `..._table.png`, row **I-695**:
R²=0.17, %RMSE=55, GEH<5=0%, bias −21%, median ratio 0.53, **FAIL**.

**Problem:** The corridor whose diversion the whole congestion-pricing study measures
is the **single worst-correlated freeway** (R²=0.17) and gets half the observed
volume. Any headline that implies the network is validated *for the corridor of
interest* is unsupported. The paper must foreground this and lean on the ΔV
(before→after difference) argument, which it does in `validate_base_hybrid.py`
markdown but not on the figures.

**Fix:** State the I-695 base fit explicitly wherever the corridor result is claimed;
do not let "ALL mainline PASS" stand in for I-695 validity.

---

## MAJOR

### M1. "R²" reported everywhere is squared Pearson correlation, not the coefficient of determination — and the model has a −33% bias that only R² penalises
**Where:** `netval2023_common.py`/`validate_base_hybrid.py:67` `corr2=float(r*r)`;
`robust_match_aadt_2023.py:361-362` `c**2`; `make_nyc_style_figures.py:36`
`np.corrcoef(...)**2`; column labeled `R2` in `route_validation_summary.csv`;
on-figure `$R^2$ = 0.76` in `aadt_ALL_mainline_loglog.png`; footnote
"R² ≥ 0.70 satisfactory".

**Problem:** Squared Pearson correlation is invariant to scale and offset, so it is
**blind to the model's systematic under-assignment**. The cleaned tables show
ALL-mainline **median bias −33%, mean bias −24%** (`base_speedfix/per_facility_table_clean.csv`)
and freeway median ratio 0.56. The true coefficient of determination vs the 1:1 line
(R² = 1 − SSres/SStot) would be far lower — plausibly negative on the biased freeway
subset — yet the figures label the 0.76/0.77 correlation² as "R²" and cite an
"R²≥0.70 satisfactory" standard. Calling r² "R²" in a validation table overstates fit
for a biased model. (Note: `compare_figures.py:80-86` actually computes *both* r² and
the real 1−SSres/SStot but the figures display only r², labeled "R²(corr)".)

**Fix:** Either label it honestly as "squared correlation (r²)" and stop citing an
"R²≥0.70" acceptance standard for it, or report the genuine coefficient of
determination alongside — it will expose the bias the correlation hides.

### M2. Two validation artifacts give OPPOSITE verdicts on the same metric via different thresholds
**Where:** `validate_base_hybrid.py:305,336` gates ALL-mainline corr²≥**0.80**
→ `base_speedfix/gate.json` `all_mainline_corr2=0.789` → `pass:false`, **GATE_PASS=false**.
Meanwhile `route_validation_summary.csv` gates the same metric at **R²≥0.70** → **PASS**.

**Problem:** The identical quantity (pooled corr²≈0.76–0.79) is declared FAIL by the
gate script and PASS by the route table, because the thresholds differ (0.80 vs 0.70)
with no stated justification. A reader handed both artifacts gets contradictory
conclusions.

**Fix:** Pick one threshold with a cited basis and apply it in both places.

### M3. Selective "bad-match" cleaning drops model=0 stations from corr² — that removes genuine under-predictions, not just geometry errors
**Where:** `validate_base_hybrid.py:82-95`. `bad_match = (ratio>=2.5) | (model_daily<=0)
| (ramp-on-mainline) | (min_dist>1.5·tol)`; the cleaned table is the one fed to the gate.

**Problem:** `model_daily<=0` is treated as a "bad match" and dropped. A zero simulated
volume at a real station is frequently a **true model failure** (no resident demand
routed there), not a snapping error. Dropping zeros and high-ratio over-matches is a
one-directional filter that *raises* corr² and %GEH<5: ALL-mainline corr² moves
0.759→0.789 raw→clean (`per_facility_table.csv` vs `..._clean.csv`), and Collector/Local
0.172→0.301. The count of drops is disclosed in the markdown, but the metric
improvement and its upward direction are not.

**Also (M3b):** The raw ALL-mainline `meanbias = −1.8%` (`per_facility_table.csv`, and
"+3%" on the route table / loglog figure) is an artifact of a handful of ratio≥2.5
over-predictions offsetting the pervasive under-prediction. After those are dropped the
mean bias is **−24%** and the median is **−33%**. Printing "mean bias = +3%" on a
scatter whose point cloud visibly sits *below* the 1:1 line
(`aadt_ALL_mainline_loglog.png`) is misleading — quote the median bias (−28 to −33%).

**Fix:** Keep model=0 stations in the accuracy statistics (they are model behaviour),
or separate "unmatched" from "matched-but-zero." Report median bias, not the
outlier-inflated mean, as the headline bias.

### M4. Speed-audit figure 1: the "freeway free-flow std 65" narrative is contradicted by its own bars (median ≈ 50 mph)
**Where:** `speed_audit.py:181-186` + `FINAL_FIGURES/speed_audit/1_realized_speed_by_facility_tod.png`;
data in `speed_audit/realized_speed_by_facility_tod.csv`.

**Problem:** The figure draws a dashed reference at **65** ("freeway free-flow std 65")
and another at **47** ("broken-cal 47 (reverted)"), and the docstring claims off-peak
freeways return "back at facility standard (~65, not the broken 47)." But the Freeway
bars sit at **~50 mph in every period** (free-flow 50.0, AM peak 49.3) — only ~3 mph
above the "broken" 47 line and **15 mph below** the 65 line the figure anchors on. The
cause: `facility()` (`speed_audit.py:54-56`) lumps `trunk` (50-mph standard, 6,386
links per `network_audit_summary.csv`) with `motorway` (65-mph, 5,280 links) into one
"Freeway" class, so the pooled median is pulled to the trunk value. The 65 line is only
valid for motorways (the pure-motorway corridor table shows I-95 at 65, I-695 at 61).

**Why misleading:** A reader sees a "Freeway" bar sitting just above the "broken/reverted"
line, next to a 65 standard line it never reaches, under a caption asserting the speeds
are fixed and back at standard. The reference line and the pooled category disagree.

**Fix:** Split motorway vs trunk (draw 65 for motorway, 50 for trunk), or relabel the
line to the pooled expectation. Report the motorway-only median (which does approach 65).

### M5. Freeway under-count (−44%) is attributed on-figure to "through passenger cars" — an unsupported causal claim stated as fact
**Where:** `aadt_ALL_mainline_loglog.png` footnote: *"Below-1:1 residual = through
passenger cars."*; `validate_base_hybrid.py:371-378` framing text ("~−35% low … matches
MATSim-NYC's −29 to −40%").

**Problem:** Every point below the 1:1 line is asserted to be unmodeled through-traffic.
The x-axis is already passenger-car AADT (freight removed), and there is **no independent
through-traffic estimate on the figure** to support the attribution — the residual could
equally be resident trip under-generation, capacity, or assignment error. Two quantitative
overreaches compound it: (a) the framing says "~−35% low" but the cleaned freeway median
bias is **−44%** and ALL-mainline median **−33%**; (b) freeway −44% is **outside** the
cited "−29 to −40%" NYC band, yet is claimed to match it.

**Fix:** Present the residual as "under-assignment (largest on freeways)" without asserting
the mechanism, or cite an independent through-traffic share. Correct "~−35%" to the actual
−44% freeway / −33% all-mainline; drop or qualify the NYC-band match.

### M6. Base freeways are essentially uncongested, undercutting the "congestion diagnostics" framing
**Where:** `speed_audit.py:277-327` + figs 4/5; `speed_audit/congestion_diagnostics.csv`,
`key_corridor_speeds.csv`.

**Problem:** Freeway median realized speed goes 50.0 (off-peak) → 49.3 (AM peak): a
**−0.7 mph / −1.5%** peak drop, with only 18.9% of freeway VMT below 0.75×free-flow.
I-695 goes 61.3→59.5 (−1.8 mph). Figure 4's title ("drop from off-peak = congestion
forming") and figure 5 ("does travel actually slow at the peaks?") present ~2% speed
drops as congestion. For a congestion-pricing paper this is material: if the base
freeway network barely congests, the modeled travel-time benefit of an I-695 toll is
near the noise floor, and the speed figures should not imply otherwise.

**Fix:** State plainly that modeled peak freeway congestion is mild (≈2% speed drop,
~19% VMT) and discuss what that implies for the toll's measurable benefit; avoid
"congestion forming" captions over near-flat bars.

---

## MINOR

### m1. I-695 panel acceptance band on the standards table doesn't match the band actually gated
**Where:** `validate_base_hybrid.py:293-296,315`. The gate computes
`med_ok = 0.35<=med<=0.75` and `bulk = ratio.between(0.20,1.20)`, but the standards-table
row prints the resident standard as **"0.30-0.90, no zeros"**. Three different bands
(0.35–0.75, 0.20–1.20, 0.30–0.90) for one check; the printed standard matches neither the
median gate nor the bulk gate.

**Fix:** Print the exact band the gate enforces.

### m2. "Freeway rel-bias PASS" is defined as −50%…−15% — i.e. a 15–50% under-count is a PASS
**Where:** `validate_base_hybrid.py:310-311,330`. Defensible under the declared
resident-only scope, but a reviewer should see it stated that the "PASS" means
"consistently under by 15–50%," not "accurate." The freeway value gated to PASS is −44%.

**Fix:** Rename the verdict (e.g. "consistent-scope") so PASS is not read as accuracy.

### m3. Network has residential/local links at 80.5 mph (self-flagged, not fixed)
**Where:** `network_audit/network_audit_summary.csv` (Residential/Local max_mph 80.5;
every class shows max 80.5) and `network_audit_anomaly_flags.csv`
(`nonfreeway_gt66mph_likely_miscode = 894`, `local_above_45mph = 391`,
`above_motorway_std_gt66mph_all = 1027`). The audit honestly flags these but they remain
in the run network. 894 miscoded high-speed non-freeway links can distort routing/speed
choice. Median residential is fine (9.3 mph); the tail is not.

**Fix:** Cap/repair the flagged links or document why they are immaterial to assignment.

### m4. ABIT trip-length and mode-share failures are recorded but the track is described as "validated"
**Where:** `ABIT/validation/rts_tripgen_dist/validation_triplength.csv` (WORK −41.6%,
SHOP −45.6%, OTHER −32.9% — all FAIL; only SCHOOL passes), `validation_mode.csv`
(car_driver +20.6%, transit −52.6%), `validation_before_after.csv` (tours/person FAIL
all scopes; tripshare_SCHOOL −96% FAIL). The CSVs and `before_after.py:151` ("±10% gate",
red FAIL cells) are honest, but any prose calling ABIT demand "validated vs RTS" is not
supported by 3-of-4 failing trip lengths and a +20% car-share skew. Relevant here because
these trips are the demand the MATSim assignment consumes — the −33% link under-count and
the too-short trip lengths are consistent and possibly linked.

**Fix:** Describe ABIT demand as "partially validated (volumes/spatial R² strong; trip
lengths short by 30–46%, car share high)"; note the interaction with the link under-count.

### m5. Route-figure and %RMSE generators are not in the repo — not independently reproducible
**Where:** No script under `code/` produces `route_validation_summary.csv`,
`facility_before_after_passenger.csv`, or the `aadt_validation_by_route/*` figures
(grep for `fac_band_pct`/`within_facband`/`%RMSE` finds only the output CSVs). The
%RMSE=100% denominator and the PASS logic therefore can't be verified against source.

**Fix:** Commit the generator so the PASS gate and %RMSE definition are auditable.

---

## What's solid (credit where due)
- **GEH formula is correct** everywhere: `sqrt(2(m−o)²/(m+o))`
  (`netval2023_common.py:105-109`, `robust_match_aadt_2023.py:63-67`).
- **×10 sample scaling is applied exactly once and consistently.** `vol24 = HRS0-24avg×10`
  in `load_linkstats` (`netval2023_common.py:75`), summed once by `sim_daily_lookup`; the
  `aadt_validation_2023_cleaned.csv` `model_daily` is pre-scaled and downstream code does
  not re-scale (confirmed and documented in `select_resident_targets_2023.py:16-24`).
  flowCapacityFactor=0.10 in `RunBaltimoreToll.java:109`. No double-application found.
- **Station→link matching is careful and conservative:** facility-gated snap tolerances,
  same-class OSM gate, ramp rejection for mainline counts, name/capacity gates, and
  correct **bidirectional carriageway summing** via anti-parallel pairing (dot<−0.7),
  which biases toward *under*-count (single-carriageway matches), i.e. against the model —
  not a headline-inflating error (`robust_match_aadt_2023.py:198-230`,
  `validate_base_hybrid.py:236-262`).
- **The calibration/held-out split is honest** — through routes, ramps, freeways,
  high-commercial and extreme-ratio stations are excluded from calibration, with a
  deterministic 25% OOS reserve and an explicit leak sanity-check
  (`select_resident_targets_2023.py:107-141,231-244`). Freight exclusion uses the correct
  class fields (SINGLE_UNIT+COMBINATION_UNIT+BUS, lines 76-79).
- **gate.json does not lie:** GATE_PASS=false, freeway bias −44%, transit 1.10, panel n/a
  are all written faithfully (`base_speedfix/gate.json`). The failure is real and recorded;
  it is only the *route-table PASS layer and some captions* that over-sell it.
- **The headline loglog scatter is itself honest** — it prints %RMSE=100%, GEH<5=6%,
  within-band=17%, and colours 1,732/2,108 points red as "outside both bands." The issue is
  the PASS verdict and the two footnote claims (M1, M5), not the plotted data.
- **network_audit** correctly reports full strong-connectivity (1 SCC, 0 islands) and
  self-flags its own speed anomalies rather than hiding them.

---

## Top-line summary for the authors
The validation *code* is sound and the *data artifacts are honest*; the model genuinely
runs ~−33% low on links (−44% on freeways), meeting 0 of 3 standard FHWA/NCHRP link-count
criteria. The defensible framing is the one already in `VALIDATION_HYBRID.md` — resident-only
scope, ΔV robustness — **not** an "ALL-mainline PASS." Before submission: (1) drop the
OR-gate PASS on pooled r² (C1) and foreground I-695's R²=0.17 (C2); (2) stop labeling squared
correlation as "R²" with an "R²≥0.70" standard (M1) and reconcile the 0.80-vs-0.70 threshold
contradiction (M2); (3) fix the speed-figure 65-line/50-mph contradiction (M4) and the
"through passenger cars" causal claim + the −35%/−44% number (M5); (4) report median (not
mean) bias on figures (M3b).
