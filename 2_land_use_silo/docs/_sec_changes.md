# 8. Changes introduced in this project (VAE-SILO drop-in)

This section documents the modifications made so that SILO runs correctly on the **VAE-generated
synthetic population** and reproduces the observed year-by-year ACS trajectories. They fall into
three groups: (A) environment/build changes that make the run execute at all; (B) source-code and
data fixes that correct model behaviour on the VAE population; and (C) the validation framework
added around the run. A set of earlier VAE-SILO model calibrations already present in the code
tree (dated 2026-06-11 … 06-20) is summarized at the end.

## 8.A Environment and build changes (make the run execute)

These do not change model logic; they make SILO runnable on the VAE population on this machine.

1. **Corrected classpath.** `mvn dependency:build-classpath` resolved a *stale* `.m2` copy of
   `siloCore` that lacked `EducationModelMstm`. Fix: put the freshly-built local reactor jars
   first — `maryland.jar : siloCore/target/siloCore.jar : matsim2silo.jar : <deps>`.
2. **x86-64 JVM + native HDF5.** SILO reads OMX travel-time skims through the NCSA `jhdf5` JNI
   library, which is **x86-64 only**; it will not load into an arm64 JVM. Fix: run the x86-64
   **JDK 21** (`temurin-21-x64`) and stage `libjhdf5.dylib`/`libjhdf.dylib` on
   `-Djava.library.path`.
3. **Vacant-job buffer.** The VAE `jj` had every job filled (1:1 with workers). SILO's labor
   market needs vacant jobs (the reference MSTM file is ~27% vacant), otherwise `findVacantJob`
   floods "No jobs remaining". Fix: append vacant jobs (`personId = -1`) so the stock matches the
   proven ~8.4M total, keeping the filled-job IDs unchanged so `pp.workplace` links survive.

## 8.B Source-code and data fixes (correct model behaviour)

### 8.B.1 `findVacantJob` array-overflow crash (siloCore)

**Symptom.** The run crashed in year 2018 with
`ArrayIndexOutOfBoundsException: Index 31 out of bounds for length 31` in
`Sampler.incrementalAdd`, from `JobDataManagerImpl.findVacantJob`.

**Cause.** The `regionSampler` is allocated with capacity `regions.size()` (31). The first loop
adds regions weighted by commuting-time probability. If *all* those weights come out 0 (a
job-seeker whose home zone is beyond the commute distribution's support from every region with
vacancies), the cumulative probability is 0 and a **fallback loop re-adds** regions to the *same*
sampler — but the internal `index` has already advanced, so it overflows.

**Fix.** Reallocate the sampler before the fallback loop so its index resets:

```java
// JobDataManagerImpl.findVacantJob  (the fallback branch)
if (regionSampler.getCumulatedProbability() == 0) {
    // fix: use a FRESH sampler so the incrementalAdd index resets (the first
    // loop already advanced it; re-adding here overflowed the 31-slot array)
    regionSampler = new Sampler<>(regions.size(), Region.class, SiloUtil.getRandomObject());
    for (Region reg : regions) {
        if (getNumberOfVacantJobsByRegion(reg.getId()) > 0) {
            int tt = (int) (travelTimes.getTravelTimeToRegion(homeZone, reg, peakHour, car) + 0.5);
            regionSampler.incrementalAdd(reg, 1.0 / Math.max(1, tt));   // inverse-distance fallback
        }
    }
}
```

With this fix the run completes all years 2016 → 2023.

### 8.B.2 `pp.workplace` person↔job linkage (data + source)

**Symptom.** 2.4M "referenced non-existing job" warnings; SILO repeatedly cleared and re-matched
workplaces.

**Cause.** The VAE workplace-allocation step wrote the **work zone** into `pp.workplace` instead
of the **job id**. Among 6.09M employed persons there were only ~1,585 distinct workplace values
(all in 1–1674, i.e. zone IDs), so the person→job link was effectively random; the job→person
link (`jj.personId`) was correct.

**Fix (data).** Rebuild `pp.workplace` by inverting `jj.personId` (job→person becomes
person→job), yielding a perfect bijection (6,091,727 unique job IDs, 100% valid, 100% consistent
with `jj.personId`).

**Fix (source).** Correct the generator so regenerations are right:

```python
# vaelib/workplace.py  (assign)  — before:  wp[pid] = z   (the work zone)
wp[int(pid)] = jid                 # SILO workplace = JOB id (not zone); job created next line
jj.append((jid, z, int(pid), "job")); jid += 1
```

> Note: this was a genuine data error worth fixing (it broke job-fill and produced millions of
> spurious warnings), but it was **not** the cause of the income/autos inflation — re-running with
> it fixed left those metrics unchanged. The real causes are 8.B.3 and 8.B.4.

### 8.B.3 Job-market forecast method: `interpolation` → `rate` (properties)

**Symptom.** A one-year *step* in household income (median bias +14–28%) and autos (mean
1.64 → 1.78) at the first simulated year, then flat — not a gradual drift.

**Cause.** With `job.forecast.method = interpolation`, `JobMarketUpdate` targets an exogenous MSTM
forecast file whose **2016 per-zone/type** job distribution differs from the VAE workplace
allocation by **2.35M jobs (28%)** (the *totals* match within 1%; the *spatial* distribution does
not). `JobMarketUpdate` "corrected" this in year 2016 by removing surplus jobs — exhausting the
vacancy buffer and **firing ~668k workers (11% of the workforce)** — who were then re-hired and
re-anchored to the demographic-cell mean income.

**Fix.** Switch to the **rate** method, whose base-year forecast equals the *actual* SP job counts
per zone/type (zero base-year reshuffling), growing uniformly thereafter:

```
# siloMstm_uvae_2023.properties
job.forecast.method      = rate      # was: interpolation
job.growth.rate          = 1.0       # ~1%/yr, matches regional employment + population growth
```

This eliminated the 11% firing (confirmed: 0 forced firings in year 2016).

### 8.B.4 `takeNewJob` income preservation (siloCore) — the income/autos root cause

**Symptom.** Even after 8.B.2 and 8.B.3, household income still inflated identically: the employed
median jumped +24% in the first two years and froze. A per-person trace showed income is
*preserved* in year 2016 (corr 0.997, freeze-and-grow) but **reverts toward the cell mean in
2017** (corr 0.862; the $0–20k bin grows ×1.26, the $150k+ bin shrinks ×0.90 — both pivoting on
the cell mean).

**Cause.** SILO re-matches essentially every worker to a (renumbered) job each year. `takeNewJob`
overwrote each re-hire's income with `getAverageIncome(gender, age, occupation)` — the demographic
**cell mean**. Because earnings are right-skewed (mean ≈ 36% above median), re-anchoring ~all
workers to the mean every year collapses the distribution **upward**, inflating the household
median and cascading into the income-sensitive auto-ownership model. (`IncomeAdjustment` itself is
correct freeze-and-grow; it is not the culprit.)

**Fix.** Preserve the worker's existing earnings when they already have some; only genuine new
entrants (no prior income) are anchored to the cell target. `IncomeAdjustment` then applies the
single real-wage-growth step at year-end.

```java
// EmploymentModelImpl.takeNewJob
// BEFORE:
final int inc = Math.max((int) (avgIncome * wageGrowthFactor) + change[sel], 0);   // cell MEAN
person.setIncome(inc);

// AFTER (2026-06-25):
final int priorIncome = person.getAnnualIncome();
final int inc;
if (priorIncome > 0) {
    inc = priorIncome;                         // preserve; IncomeAdjustment grows it at endYear
} else {
    inc = Math.max((int) (avgIncome * wageGrowthFactor) + change[sel], 0);   // genuine new entrant
}
person.setIncome(inc);
```

Both code fixes (8.B.1, 8.B.4) are compiled with the x86-64 JDK 21 (Java-21 bytecode) and patched
into `siloCore-0.1.0-SNAPSHOT.jar` and `siloCore/target/classes`.

## 8.C Validation framework (added)

- `collect_yearly_output.py` — copies each simulated year's `{hh,pp,dd,jj}_<year>.csv` and the
  aggregate result files into `Updated SILO/silo_output/<year>/`.
- `validate_by_year_acs.py` — validates every SILO year against that year's **ACS PUMS 5-year**
  sample (MD/DC/DE; incomes deflated to 2016$ via CPI-U so all vintages are commensurable),
  producing per-year/per-state figures for household size, autos, dwelling type, income class,
  age, gender, race, and occupation, plus a `summary.csv`. It reuses the proven recoding from the
  project's `scripts/05d_validate_silo_by_year_acs.py`.

## 8.D Earlier VAE-SILO model calibrations already in the tree

These were applied before this session (dated comments in the source) and remain active; they
calibrate the *existing* models to ACS without altering the VAE base population:

| Date | Component | Change |
|---|---|---|
| 2026-06-11 | JobDataManagerImpl (interpolation) | Sort forecast year-columns chronologically (the MSTM file was interpolated on the wrong segment, "firing ~3.4M workers") |
| 2026-06-12 | EducationModelMstm | Recalibrated school-exit (to age 29) and retirement (start 62) hazards to MSTM ACS PUMS |
| 2026-06-13 | IncomeAdjustment / EmploymentModel | Real-wage-growth indexation; retiree drift set flat-nominal (COLA), removing −2%/yr decay |
| 2026-06-13/17/19 | InOutMigrationImpl | Per-state population control; composition-targeted migration (race + single-person marginals); per-state in-migrant placement |
| 2026-06-14 | JobDataManagerImpl | Rebuild the vacant-job index from scratch each year (was appending stale entries) |
| 2026-06-15 | IncomeAdjustment; JobMarketUpdate; adjustIncome | Freeze-and-grow employed income; CPU-bounded thread pools (prevent native-thread exhaustion at ~11.8M persons) |
| 2026-06-16 | MaryLandUpdateCarOwnershipModel | Activate + re-calibrate auto ownership per (region × worker-class); MSTM previously left new households at 0 autos |
| 2026-06-16/18 | EducationModelMstm | Retirement income replacement (0.80 of pre-retirement earnings) with a Social-Security floor (~$15k 2016$) |
| 2026-06-20 | LocalDemographicScalers | Per-state birth/marriage calibration (DC 0.72 / 0.65) to fix DC household-size drift |

## 8.E Status and the residual DC drift

The income/autos fixes (8.B.3, 8.B.4) were verified at the per-person level and are being
confirmed on a full re-run. The remaining gap is the **DC demographic drift** (household size and
age distributions drift upward over the simulated years) — a documented limit of a closed-region
microsimulation: DC's real demographics are sustained by constant in-migration of young single
adults that a closed model cannot fully reproduce, even with the per-state demographic scalers
(8.D, 2026-06-20). MD and DE track ACS closely throughout.
