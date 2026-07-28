# 6. Real estate, relocation, and auto ownership

These models evolve *where* households live, the *housing stock* they occupy, *migration* in and
out of the region, and *car ownership*.

## 6.1 Residential moves (MovesModelImpl)

A two-stage model. **Stage 1 (move-or-stay):** a household moves if its current dwelling utility
falls below the average satisfaction for its household type, via a logistic probability:

```
P(move) = 1 − 1 / (1 + 0.03 · exp(10 · (avgSatisfaction − currentUtil)))
```

```java
// MovesModelImpl.moveOrNot (lines 275–286, condensed)
final double currentUtil   = satisfactionByHousehold.get(household.getId());
final double avgSatisfaction = averageHousingSatisfaction.getOrDefault(hhType, currentUtil);
final double prob = movesStrategy.getMovingProbability(avgSatisfaction, currentUtil);
return random.nextDouble() <= prob;
```

**Stage 2 (where-to):** a region is chosen by MNL on regional utility and vacancy, then up to
`MAX_NUMBER_DWELLINGS = 20` vacant dwellings in that region are scored by a housing-utility
strategy and one is sampled. Moves are also what *execute* marriages, divorces, leaving home,
demolitions, and in-migration (each searches for a dwelling through this model). Output:
`relocation.csv`.

## 6.2 In/out migration (InOutMigrationImpl)

Drives regional population growth/decline to an exogenous control. Three modes
(`population.control.total.method`): **POPULATION** (absolute targets), **MIGRATION** (explicit
flows), **RATE** (geometric growth). In-migrants are created by **cloning** existing households
(preserving demographic structure) and placing them in vacant dwellings; out-migrants are
removed. Recent VAE-SILO additions (2026-06-13/17/19) add optional **per-state** control and
**composition-targeted** migration that nudges each state's race and single-person-household
marginals toward ACS, with bounded annual churn (≤6%).

```java
// InOutMigrationImpl.controlStateComposition (lines 312–361, condensed)
int target = (int) tblPopulationTargetByState.getIndexedValueAt(year, String.valueOf(st));
double[] marg = marginals.get(year).get(st);          // [white,black,hispanic,other,onePerson]
double[] inW = computeUnderRepresentationWeights(pool, marg);
int churn = (int) Math.min(0.06 * currentPop, 0.6 * gap * currentPop);
weightedOut(pool, inW, max(0, currentPop - target) + churn, events);
weightedIn (pool, inW, max(0, target - currentPop) + churn, events, st);
```

## 6.3 Construction (ConstructionModelImpl)

Builds new dwellings where demand is high. Per region and dwelling type, demand responds to the
**vacancy rate** relative to the type's structural vacancy α (high demand below α, decaying
above), and the **location** of new units is chosen by a log-model on
`α_type·price + γ_type·accessibility` (denser types weight accessibility more). A one-year lag
applies. Properties: `realEstate.constructionLogModelBeta`, `…Inflator`.

```java
// ConstructionModelImpl (lines 103–115, condensed)
demandByRegion[dto][region] = demandStrategy.calculateConstructionDemand(
        vacancyByRegion[dto][region], dt, dwellingsByRegion.get(region).size());
// location chosen ∝ exp(beta · (a_type·price(zone) + g_type·accessibility(zone)))
```

## 6.4 Demolition (DemolitionModelImpl) and Renovation (RenovationModelImpl)

**Demolition** removes dwellings by a probability that depends on construction era and occupancy
— vacant units are ~9× more likely to be razed; occupied units force the resident household to
relocate or out-migrate.

```
P(demolish) = vacantModifier · baseRate(yearBuilt)       vacantModifier = 0.9 vacant / 0.1 occupied
```

**Renovation** moves a dwelling's quality up or down (±1, ±2, or unchanged) each year, with the
transition probability rebalanced toward the base-year quality distribution
(`base_prob[Δ] · initialShare[target]/currentShare[target]`).

## 6.5 Pricing and vacancy (PricingModelImpl, RealEstateDataManagerImpl)

Dwelling prices adjust annually to the **regional vacancy rate** of each type relative to its
structural rate α, capped at ±10%/yr: vacancy below 0.9α drives prices up steeply, near α prices
adjust gently, above 2α prices plateau, and above 10% vacancy prices are frozen.

```java
// PricingModelImpl.updateRealEstatePrices (lines 74–100, condensed)
double changeRate = strategy.getPriceChangeRate(vacancyRateAtThisRegion, structuralVacancyRate);
dd.setPrice((int) (dd.getPrice() * changeRate + 0.5));   // changeRate clamped to [0.9, 1.1]
```

## 6.6 Auto ownership (MaryLandUpdateCarOwnershipModel)

A segmented multinomial-logit for 0/1/2/3+ vehicles. Each alternative's utility combines
alternative-specific constants with household size, number of workers, transit accessibility,
and income/density category terms:

```java
// MaryLandUpdateCarOwnershipModel.expUtilities (lines 111–120)
double one   = Math.exp(ASC_ONE   - 0.121*s + 0.327*w - 0.022*transitAcc + INC_ONE[i]   + DENS_ONE[d]);
double two   = Math.exp(ASC_TWO   + 0.689*s + 0.652*w - 0.051*transitAcc + INC_TWO[i]   + DENS_TWO[d]);
double three = Math.exp(ASC_THREE + 0.801*s + 1.378*w - 0.054*transitAcc + INC_THREE[i] + DENS_THREE[d]);
// P(k) = exp(U_k)·exp(asc_k) / (1 + Σ_j exp(U_j)·exp(asc_j))
```

This model is **income-sensitive** (`INC_*[i]`), which is why the income inflation diagnosed in
this project cascaded directly into car-ownership over-prediction. A 2026-06-16 VAE-SILO change
activated the model (MSTM previously left new households at zero autos) and re-calibrated its
alternative-specific constants per (region × worker-class) cell (with backoff to region then
global when a cell has < 300 base households), so the simulated base-year auto distribution
matches the observed one and spatial heterogeneity is preserved.
