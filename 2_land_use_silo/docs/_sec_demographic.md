# 4. Demographic models

The demographic models simulate the life-events that change *who exists* and *how households
are composed*: birth, aging, death, marriage, divorce, children leaving home, and
school/work/retirement transitions. Each is invoked once per simulated year and proposes
events for eligible agents.

## 4.1 Birth (BirthModelImpl, DefaultBirthStrategy)

Simulates childbirth for fertile-age women, stochastically adding a newborn person to the
mother's household. The annual probability layers a base age/parity rate with marital-status
and **per-state** multipliers:

```
P(birth) = localScaler · P_base(age, #children) · maritalStatusScaler · stateFactor
```

`P_base` is the age- and parity-specific base rate from `DefaultBirthStrategy` (ages 15–49,
stratified by 0–3+ existing children). Properties: `demographics.localScaler`,
`demographics.marriedScaler` / `singleScaler`, `demographics.localScalersFile`,
`eventRules.birth`.

```java
// BirthModelImpl.java  (lines 95–106)
double birthProb = localScaler * strategy.calculateBirthProbability(
        person.getAge(), HouseholdUtil.getNumberOfChildren(person.getHousehold()));
if (localScalers != null) {
    birthProb *= localScalers.birthFactor(person.getHousehold());   // per-state (DC 0.72)
}
if (person.getRole() == PersonRole.MARRIED) {
    birthProb *= properties.demographics.marriedScaler;
} else {
    birthProb *= properties.demographics.singleScaler;
}
if (random.nextDouble() < birthProb) { giveBirth(person); return true; }
```

## 4.2 Aging / birthday (BirthdayModelImpl)

Deterministic: every surviving person ages one year, which in turn can trigger occupation
transitions downstream (school entry, graduation, retirement — see §4.7).

```java
// BirthdayModelImpl.java  (lines 54–62)
private boolean checkBirthday(BirthDayEvent event) {
    Person per = dataContainer.getHouseholdDataManager().getPersonFromId(event.getPersonId());
    if (per == null) return false;     // person died or moved away
    celebrateBirthday(per);            // -> per.birthday()  (age++)
    return true;
}
```

## 4.3 Death (DeathModelImpl, DefaultDeathStrategy)

Age- and gender-specific mortality, calibrated to US life tables (hardcoded, no property knob).
Removes the deceased, handles widow(er) role changes and orphan placement.

```java
// DeathModelImpl.java  (lines 43–54)
final Person person = householdDataManager.getPersonFromId(event.getPersonId());
if (person != null) {
    if (random.nextDouble() < strategy.calculateDeathProbability(person)) {  // P(death|age,gender)
        return die(person);
    }
}
```

## 4.4 Marriage (MarriageModelMstm, DefaultMarriageStrategy)

Pairs eligible (SINGLE/CHILD) persons aged 16+ into co-habiting couples, merges households,
finds a dwelling, and assigns car ownership. The Maryland variant adds **race-homophily**
matching and **per-state** marriage calibration. Three stages:

1. **Intent** — `P(intent) = strategy.calculateMarriageProbability(person) · scale · stateFactor`
   (`stateFactor` from `LocalDemographicScalers.marriageFactor()`; single-person households get
   an extra `onePersonHhMarriageBias`).
2. **Matching** — a weighted sampler over the passive pool; in MSTM same-race weight ≈ 10000 vs
   0.001 otherwise (tuned by `interracialMarriageShare`).
3. **Age-difference** — Gaussian preference: `P(ageDiff) ∝ exp(−(ageDiff+genderBias)²·marryAgeSpreadFac)`.

```java
// MarriageModelMstm.java  (lines 240–255)
private double getMarryProb(Person pp) {
    double marryProb = strategy.calculateMarriageProbability(pp) * scale;
    Household hh = pp.getHousehold();
    if (localScalers != null) {
        marryProb *= localScalers.marriageFactor(hh);   // DC 0.65, MD/DE 1.0
    }
    if (hh.getHhSize() == 1) {
        marryProb *= properties.demographics.onePersonHhMarriageBias;
    }
    return marryProb;
}
```

## 4.5 Divorce (DivorceModelImpl, DefaultDivorceStrategy)

Dissolves MARRIED couples by person-type rate (`P = divorceProbability(personType)/2`; the `/2`
because either partner can trigger the single dissolution). Creates a separate household and
searches for a vacant dwelling; if none, the divorce is retried next year.

```java
// DivorceModelImpl.java  (lines 84–135, condensed)
Person per = householdDataManager.getPersonFromId(perId);
if (per != null && per.getRole() == PersonRole.MARRIED) {
    final double probability = strategy.calculateDivorceProbability(per) / 2;
    if (random.nextDouble() < probability) { /* split household, find dwelling */ return true; }
}
```

## 4.6 Leave parental household (LeaveParentHhModelImpl)

Moves a CHILD (in a household of ≥2) into an independent SINGLE-person household by a
person-type rate, contingent on finding a vacant dwelling.

```java
// LeaveParentHhModelImpl.java  (lines 89–100)
if (per != null && qualifiesForParentalHHLeave(per)) {
    final double prob = strategy.calculateLeaveParentsProbability(per);
    if (random.nextDouble() < prob) return leaveHousehold(per);
}
```

## 4.7 Education / occupation transitions (EducationModelMstm)

The Maryland variant handles **all** age-triggered occupation changes (the generic
`EducationModelImpl` only dropped students ≥19 to unemployed). Three transitions, recalibrated
to MSTM-region ACS PUMS 2012–16 in 2026:

- **TODDLER → STUDENT** at age 5 (deterministic; income 0).
- **STUDENT → UNEMPLOYED** ages 18–29 (annual `SCHOOL_EXIT_PROB[age]`: 0.34 at 18 … 0.15 at
  25–29, forced at 30 — reproduces ~5.7% still enrolled at 25).
- **EMPLOYED/UNEMPLOYED → RETIREE** age 62+ (`RETIREMENT_PROB_*`: employed 0.08 at 62 … 0.30 at
  85+; unemployed retire faster). On retirement, income is set to a replacement of
  pre-retirement earnings with a Social-Security floor.

```java
// EducationModelMstm.java  handleRetirement (lines 285–353, condensed)
double retireProb = isUnemployed ? RETIREMENT_PROB_UNEMPLOYED[ageIdx]
                                 : RETIREMENT_PROB_EMPLOYED[ageIdx];
if (random.nextDouble() < retireProb) {
    int preRetirementIncome = person.getAnnualIncome();
    person.setOccupation(Occupation.RETIREE);
    if (!isUnemployed && person.getJobId() > 0) dataContainer.getJobDataManager().quitJob(true, person);
    int repl = (int) (preRetirementIncome * 0.80 + 0.5);   // VAE-SILO 2026-06-18
    person.setIncome(Math.max(repl, SS_FLOOR));             // SS_FLOOR ~ $15k (2016$)
}
```

## 4.8 Per-state demographic calibration (LocalDemographicScalers)

A 2026-06-20 VAE-SILO addition that calibrates the **existing** birth and marriage models to
ACS without touching the VAE base population. It reads a CSV keyed by state FIPS and applies a
`birthFactor` / `marriageFactor` per household by its zone's state. DC (FIPS 11) gets 0.72 /
0.65 (its ACS fertility is ~28% below and married share ~35% below MD/DE); all other states stay
at 1.0.

```java
// LocalDemographicScalers.java  (lines 41–72, condensed)
TableDataSet t = SiloUtil.readCSVfile(properties.main.baseDirectory + file);
int[] st = t.getColumnAsInt("state");
double[] bf = t.getColumnAsDouble("birthFactor");
double[] mf = t.getColumnAsDouble("marriageFactor");
for (int i = 0; i < st.length; i++) { birthByState.put(st[i], bf[i]); marriageByState.put(st[i], mf[i]); }
logger.info("Per-state birth/marriage scalers ENABLED for states " + birthByState.keySet());
```

> Motivation (quoted from the source, 2026-06-20): "the forecast packed DC's population into too
> few, too-large households — avg household size drifted 2.05 → 2.37 (ACS 1.94) … DC's ACS
> fertility is 28% below MD and its married share 35% below, so DC gets birthFactor 0.72 /
> marriageFactor 0.65. This calibrates the EXISTING models to data — it is not a new model and
> does not touch the VAE-generated base population."
