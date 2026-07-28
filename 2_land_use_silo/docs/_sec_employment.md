# 5. Labor, income, and the job market

This subsystem decides who works, where, and for how much. Three models interact each year:
the **EmploymentModel** (hires/fires persons and matches them to jobs), the **JobMarketUpdate**
(grows/shrinks the stock of jobs to an exogenous forecast), and the **IncomeAdjustment**
(evolves each person's earnings). Together they are the single largest driver of household
income — and, indirectly (through the income-sensitive auto-ownership model), of car ownership.

## 5.1 EmploymentModel (EmploymentModelImpl)

At `setup()` the model measures the **labor-participation share** by age and gender from the
base population and smooths it across age (a 5-point moving average). Each year it compares the
current employment in every age×gender cell to that target share and converts the gap into a
hire probability (for the unemployed) or a quit probability (for the employed):

```
change      = share[g][age] · (employed + unemployed) − employed
changeRate  =  change / unemployed        if change > 0   // probability to find a job
            =  change / employed          if change < 0   // probability to lose a job
```

Persons then draw against `changeRate` to generate `FIND` or `QUIT` events. A `FIND` is also
forced for any person whose occupation is EMPLOYED but who holds no job (`jobId <= 0`) — a
2026-06-13 fix that prevents "employed-but-jobless" persons accumulating from migration/churn.

```java
// EmploymentModelImpl.getEventsForCurrentYear (lines 98–114)
if (pp.getOccupation() == Occupation.EMPLOYED && !employed) {
    events.add(new EmploymentEvent(pp.getId(), EmploymentEvent.Type.FIND));   // force a match
    continue;
}
if (changeRate[gen][age] > 0 && !employed) {
    if (random.nextDouble() < changeRate[gen][age]) events.add(new EmploymentEvent(pp.getId(), FIND));
}
if (changeRate[gen][age] < 0 && employed) {
    if (random.nextDouble() < Math.abs(changeRate[gen][age])) events.add(new EmploymentEvent(pp.getId(), QUIT));
}
```

A `FIND` event calls `findJob()` → `JobDataManager.findVacantJob()` and, on success,
`takeNewJob()`, which assigns the job and sets the new income. A `QUIT` releases the job and
applies a 0.6× income haircut. Properties: `demographics.labor.participation.adjuster`,
`householdData.realWageGrowthRate`, `householdData.meanIncomeChange`.

## 5.2 IncomeAdjustment — annual income evolution

`HouseholdDataManagerImpl.adjustIncome()` runs at `endYear` for every person, building
per-quintile gender×age×occupation income distributions and dispatching one `IncomeAdjustment`
task per person (on a CPU-bounded thread pool — a 2026-06-15 fix that prevented native-thread
exhaustion on the 11.8M-person population). Each occupation has its own rule:

- **Employed — freeze-and-grow** (2026-06-15): keep the worker's *own* current income and grow
  it by the real-wage factor, with mild noise — preserving the income *distribution* rather than
  reverting everyone to a cell mean. New entrants (income 0) are anchored to the quintile target.
- **Retiree** — flat-nominal drift with a Social-Security floor (~$15k 2016$); the old −2%/yr
  decay was removed (2026-06-13) because SS is COLA-indexed.
- **Unemployed** — slow decay (mean −20%/yr). **Student** — usually 0 (30% chance of < $15k).

```java
// IncomeAdjustment.selectNewIncome  EMPLOYED branch (lines 125–144)
int currentIncome = person.getAnnualIncome();
if (currentIncome <= 0) {                                   // genuine new entrant
    float target = initialIncomeDistribution[g][a][1] * regionalFactor;   // quintile cell target
    return draw(target, max(MIN_SD, target*SD_FRACTION));
}
double grown = currentIncome * wageGrowthFactor;            // freeze-and-grow (×(1+g))
double sd    = Math.max(MIN_SD, grown * SD_FRACTION * 0.5); // mild idiosyncratic noise
return Math.max(0, (int) (grown + N(0, sd)));
```

> Why this matters for this project: `IncomeAdjustment` is freeze-and-grow and **preserves**
> income. But `takeNewJob` (below) historically *overwrote* a re-hire's income with the
> demographic-cell **mean**. Because SILO re-matches essentially every worker to a (renumbered)
> job each year, that re-anchoring — not `IncomeAdjustment` — was collapsing the income
> distribution upward. The fix is in §"Changes".

## 5.3 New-hire income in takeNewJob

`takeNewJob` sets the income of a person who has just found a job. The base-year code anchored
it to `getAverageIncome(gender, age, occupation)` — the **cell mean** — indexed by the real-wage
factor, plus a ±$5000 draw:

```java
// EmploymentModelImpl.takeNewJob (base-year logic, lines 259–270)
float avgIncome = householdDataManager.getAverageIncome(gender, age, person.getOccupation());
float wageGrowthFactor = (float) Math.pow(1.0 + g, Math.max(0, currentYear - startYear));
final int inc = Math.max((int) (avgIncome * wageGrowthFactor) + change[sel], 0);
person.setIncome(inc);
```

This is the line modified by this project (see §"Changes") to preserve the worker's existing
earnings instead of re-anchoring to the mean.

## 5.4 JobMarketUpdate — growing/shrinking the job stock

Each year `JobMarketUpdateImpl` compares the current number of jobs in every (zone, industry)
cell to the **employment forecast** and queues `AddJobsDefinition` (create vacant jobs) or
`RemoveJobsDefinition` (remove jobs — vacant first, then occupied via `firePerson`→`quitJob`):

```java
// JobMarketUpdateImpl.updateJobInventoryMultiThreadedThisYear (lines 100–121, condensed)
int forecast = (int) jobDataManager.getJobForecast(year, zoneId, jt);
int change = forecast - jobsByZone[JobType.getOrdinal(jt)][zoneId];
if (change > 0) executor.addTaskToQueue(new AddJobsDefinition(zone, change, jt, ...));
else if (change < 0) executor.addTaskToQueue(new RemoveJobsDefinition(zone, -change, jt, vacantJobs, occupiedJobs, ...));
```

`RemoveJobsDefinition` removes vacant jobs first and only fires workers if vacancies are
insufficient. The mismatch between our base job distribution and the forecast file is therefore
what determined how many workers were displaced — central to one of the fixes in §"Changes".

## 5.5 The employment forecast (JobDataManagerImpl)

`calculateEmploymentForecast()` offers two methods, selected by `job.forecast.method`:

- **INTERPOLATION** — reads an exogenous CSV of (zone × industry) job counts at fixed years and
  linearly interpolates between them. The forecast targets are independent of the loaded
  population. (A 2026-06-11 fix sorts the year columns chronologically; previously the MSTM file
  was interpolated on the wrong segment, "firing ~3.4M workers".)
- **RATE** — counts the *actual* jobs in the synthetic population at the base year, then grows
  each (zone, industry) cell geometrically by `job.growth.rate`. Because the base-year forecast
  equals the loaded population, there is **no base-year reshuffling**.

```java
// JobDataManagerImpl.calculateEmploymentForecastWithRate (lines 178–198, condensed)
for (Job job : jobData.getJobs())                       // base-year forecast = SP counts
    jobCountBaseyear.get(job.getZoneId()).merge(job.getType(), 1f, Float::sum);
... for each later year:
    count = base * Math.pow(1 + growthRateInPercentByJobType.get(jobType)/100, year - startYear);
```

`findVacantJob()` selects a region for a job-seeker with a `Sampler` weighted by
`commutingTimeProbability(travelTime) × numberOfVacantJobs`; if every weight is 0 it falls back
to inverse-distance weighting. `identifyVacantJobs()` rebuilds the vacant-job index from scratch
each year (2026-06-14 fix — it previously only appended, leaving stale entries). The
`findVacantJob` fallback path is where this project fixed an array-overflow crash (§"Changes").
