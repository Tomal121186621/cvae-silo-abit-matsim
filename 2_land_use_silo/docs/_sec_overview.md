# SILO Land-Use Microsimulation: Models, Mechanisms, and the VAE-SILO Modifications

**A technical reference for the VAE → SILO → MITO → MATSim pipeline (Baltimore–Washington MSTM region)**

This document describes, in detail, every model inside the SILO (Simple Integrated Land-Use
Orchestrator) land-use microsimulation as configured for the Maryland Statewide Transportation
Model (MSTM) region, the factors and mechanisms that drive each model, and how a *synthetic
base-year population* is evolved year-by-year into a *predicted* future-year population. It then
documents the specific code and configuration changes introduced in this project.

Code references point at the working tree
`/Users/tomal/Documents/SILO Simulation/silo-master/` — the core engine lives in the
`siloCore` module (`siloCore/src/main/java/de/tum/bgu/msm/…`) and the region-specific wiring in
the Maryland use case (`useCases/maryland/src/main/java/de/tum/bgu/msm/…`).

## 1. Where SILO sits in the pipeline

The end-to-end pipeline produces an agent-based travel demand simulation in four stages:

1. **VAE (population synthesis).** A conditional variational auto-encoder, trained on ACS PUMS
   microdata, generates the **synthetic base-year (2016) population** — households, persons,
   dwellings, and jobs — as CSV files in the SILO input schema. This is SILO's starting state.
2. **SILO (land use).** Reads the base-year population and **simulates demographic, labor,
   income, real-estate, and auto-ownership change one year at a time** from the base year to
   the end year (here 2016 → 2023), writing a full microdata population for every year.
3. **MITO (travel demand).** Consumes a SILO-year population and generates trips / tours
   (disabled in the runs documented here — `mito.run.travel.model = false`).
4. **MATSim (assignment).** Routes the trips on the network (not run here).

SILO is therefore the **temporal engine**: it takes the one-shot VAE cross-section and turns it
into a consistent time series of populations, each of which can be validated against the
corresponding ACS PUMS 5-year sample.

## 2. The microsimulation paradigm

SILO is an **event-based microsimulation**. Each simulated year, every model proposes
*events* (a birth, a death, a marriage, a job change, a move, …) for individual agents; the
`Simulator` collects and applies them, then the year is summarized and (optionally) written
out. The core run loop is a single pass over the years:

```java
// SiloModel.runYearByYear  (siloCore/.../SiloModel.java)
for (int year = properties.main.startYear; year < properties.main.endYear; year++) {
    // ... per-year setup (skims, accessibility) ...
    simulator.simulate(year);      // generate + process all events for this year
    dataContainer.endYear(year);   // age the population, adjust income, write per-year output
}
SiloUtil.summarizeMicroData(properties.main.endYear, modelContainer, dataContainer);
```

Three properties govern the horizon and outputs:

| Property | Value (this project) | Meaning |
|---|---|---|
| `base.year` | 2016 | Year of the VAE synthetic population (SILO's initial state) |
| `end.year` | 2023 | Last simulated year |
| `household.intermediates.file.ascii` etc. | non-empty (default) | Write full hh/pp/dd/jj microdata **every** year, not just base+end |

Because the intermediate-file properties are non-empty, `HouseholdDataManagerImpl.endYear`
writes `hh_<year>.csv` / `pp_<year>.csv` (and the dwelling / job managers write
`dd_<year>.csv` / `jj_<year>.csv`) for each simulated year into
`scenOutput/<scenario.name>/microData/`.

## 3. Input and output schema (hh / pp / dd / jj)

SILO reads and writes four linked CSV files. The links are: a **person** belongs to a
**household** (`hhID`) and may hold a **job** (`workplace` = job `id`); a **household** occupies
a **dwelling** (`dd.hhID`); a **dwelling** and a **job** each sit in a **zone**.

```
hh : id, dwelling, hhSize, autos, income, race
pp : id, hhID, age, gender, race, occupation, driversLicense, workplace, income, nationality, relationShip
dd : id, zone, type, hhID, bedrooms, quality, monthlyCost, restriction, yearBuilt
jj : id, zone, personId, type
```

The critical cross-file invariant — central to one of the fixes in §"Changes" — is that
`pp.workplace` must equal the `jj.id` of the job that person holds, and that job's
`jj.personId` must equal the person's `pp.id`. A vacant job has `personId = -1`.
