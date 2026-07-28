# 7. Simulation engine, model order, and data flow

Having described the individual models, this section shows how they are orchestrated each year
and how data flows from the input CSVs to the per-year output CSVs.

## 7.1 Entry point and run phases

`SiloMstm.main` loads the properties, builds the data container, reads the input population,
assembles the model container, registers result monitors, and runs the model in three phases —
`setupModel()`, `runYearByYear()`, `endSimulation()`.

```java
// SiloMstm.main (useCases/maryland/.../run/SiloMstm.java, lines 24–44, condensed)
Properties properties = SiloUtil.siloInitialization(args[0]);
DataContainer dataContainer = DataBuilder.buildDataContainer(properties, config);
DataBuilder.readInput(properties, dataContainer);                       // read hh/pp/dd/jj
ModelContainer modelContainer = ModelBuilderMstm.getModelContainerForMstm(dataContainer, properties, config);
SiloModel model = new SiloModel(properties, dataContainer, modelContainer);
model.addResultMonitor(new DefaultResultsMonitor(dataContainer, properties));
model.runModel();
```

## 7.2 The year loop

```java
// SiloModel.runYearByYear (siloCore/.../SiloModel.java, lines 126–156, condensed)
for (int year = properties.main.startYear; year < properties.main.endYear; year++) {
    logger.info("Simulating changes from year " + year + " to year " + (year + 1));
    dataContainer.prepareYear(year);                       // skims/accessibility/vacancy refresh
    SiloUtil.summarizeMicroData(year, modelContainer, dataContainer);
    simulator.simulate(year);                              // generate + process all events
    dataContainer.endYear(year);                           // age, adjust income, WRITE hh/pp/dd/jj_<year>
}
// after the loop: endSimulation() writes the final (endYear) population
```

## 7.3 Model registration and execution order

`ModelBuilderMstm` wires the models and registers them with the `Simulator`. The annual
execution order is: **Birth → Birthday(aging) → Death → Marriage → Divorce → DriversLicense →
Education → Employment → LeaveParentHh → JobMarketUpdate → Construction → Demolition → Pricing →
Renovation → ConstructionOverwrite → InOutMigration → Moves → (Transport)**. Car ownership is
registered as a model-update listener that runs each year.

```java
// ModelBuilderMstm (useCases/maryland/.../run/ModelBuilderMstm.java, lines 152–162)
// VAE-SILO 2026-06-15: MSTM wired NO car-ownership update model, so new / in-migrant
// households kept 0 autos (882k new households at 57.8% zero-car dragged the region 9.2% -> 16.8%).
modelContainer.registerModelUpdateListener(
        new MaryLandUpdateCarOwnershipModel(dataContainer,
                dataContainer.getAccessibility(), properties, SiloUtil.provideNewRandom()));
```

## 7.4 The Simulator (event-based core)

Each year the `Simulator` collects the events proposed by every model into one list, **shuffles**
them (so the order of life-events is randomized across agents), and processes each through its
handler:

```java
// Simulator.java (lines 76–118, condensed)
public void simulate(int year) { prepareYear(year); processEvents(); finishYear(year); }

private void prepareYear(int year) {
    for (ModelUpdateListener l : modelUpdateListeners) l.prepareYear(year);  // annual models
    for (EventModel<MicroEvent> m : models.values()) {
        m.prepareYear(year);
        events.addAll(m.getEventsForCurrentYear(year));                       // birth, death, find-job, move…
    }
    Collections.shuffle(events, SiloUtil.getRandomObject());
}
private void processEvents() {
    for (MicroEvent e : events) models.get(e.getClass()).handleEvent(e);      // apply each event
}
```

## 7.5 Readers and writers (the I/O schema)

`DataBuilder.readInput` reads zones, then households, persons, dwellings, jobs from year-suffixed
CSVs. The **Maryland** readers/writers extend the core schema with `race` (and household
`income`); the writers used at `endYear` are the `…Mstm` variants, so the output carries those
columns:

| File | Output columns (Maryland writers) |
|---|---|
| hh | `id, dwelling, hhSize, autos, income, race` |
| pp | `id, hhID, age, gender, race, occupation, driversLicense, workplace, income, nationality, relationShip` |
| dd | `id, zone, type, hhID, bedrooms, quality, monthlyCost, restriction, yearBuilt` |
| jj | `id, zone, personId, type` |

```java
// HouseholdDataManagerMstm.endYear (useCases/maryland/.../data/HouseholdDataManagerMstm.java, 178–196)
public void endYear(int year) {
    delegate.endYear(year);
    // Patch 2026-04-30: re-write hh + pp with Mstm writers so race + hh.income survive the round-trip.
    new HouseholdWriterMstm(getHouseholds()).writeHouseholds(outDir + "/hh_" + year + ".csv");
    new PersonWriterMstm(this).writePersons(outDir + "/pp_" + year + ".csv");
}
```

Per-year writing is enabled because the `*.intermediates.file.ascii` properties are non-empty;
otherwise only the base and end years would be written. Files land in
`scenOutput/<scenario.name>/microData/`.

## 7.6 Accessibility and travel-time skims

Models that involve location (moves, construction, job search) read zone-to-zone travel times.
`AccessibilityImpl.calculateHansenAccessibilities(year)` builds Hansen accessibility from the
travel-time skims and the employment/dwelling distribution; travel times come through a
`TravelTimesWrapper` backed by `SkimTravelTimes` (reads OMX matrices — the native-HDF5 dependency
that required the x86-64 JVM in this project, see §8) or by MATSim when coupled.

```java
// AccessibilityImpl.calculateHansenAccessibilities (siloCore/.../AccessibilityImpl.java, 83–100, condensed)
final Map<Integer, List<Job>> jobsByZone = jobData.getJobs().stream().collect(groupingBy(Location::getZoneId));
IndexedDoubleMatrix1D employment = new IndexedDoubleMatrix1D(geoData.getZones().values());
for (int zoneId : geoData.getZones().keySet())
    employment.setIndexed(zoneId, jobsByZone.getOrDefault(zoneId, List.of()).size());
// accessibility(i) = Σ_j employment(j) · f(traveltime(i,j))
```
