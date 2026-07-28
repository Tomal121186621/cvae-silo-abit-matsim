package abm.models.modeChoice;

import abm.data.DataSet;
import abm.data.geo.RegioStaR2;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.pop.Relationship;
import abm.io.input.CoefficientsReader;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.nio.file.Path;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;

public class NestedLogitHabitualModeChoiceModel implements HabitualModeChoice {
    private final static Logger logger = LogManager.getLogger(NestedLogitHabitualModeChoiceModel.class);

    private final DataSet dataSet;
    private Map<HabitualMode, Map<String, Double>> coefficients;

    private boolean runCalibration = false;
    private Map<Occupation, Map<HabitualMode, Double>> updatedCalibrationFactors;

    public NestedLogitHabitualModeChoiceModel(DataSet dataSet) {
        this.dataSet = dataSet;
        this.coefficients = new HashMap<>();
        Path pathToCoefficientsFile = Path.of(AbitResources.instance.getString("habitual.mode.coef"));

        //the following loop will read the coefficient file Mode.getModes().size() times, which is acceptable?
        //Todo the modes in the habitual mode choice model is not consistent with the ABIT mode definition. Check with Carlos and Joanna
        for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
            final Map<String, Double> modeCoefficients = new CoefficientsReader(dataSet, habitualMode.toString().toLowerCase(), pathToCoefficientsFile).readCoefficients();
            coefficients.put(habitualMode, modeCoefficients);
        }
    }

    public NestedLogitHabitualModeChoiceModel(DataSet dataSet, Boolean runCalibration) {
        this(dataSet);
        this.updatedCalibrationFactors = new HashMap<>();
        for (Occupation occupation : Occupation.values()) {
            this.updatedCalibrationFactors.putIfAbsent(occupation, new HashMap<>());
            for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
                this.updatedCalibrationFactors.get(occupation).putIfAbsent(habitualMode, 0.0);
            }
        }
        this.runCalibration = runCalibration;
    }


    @Override
    public void chooseHabitualMode(Person person) {

        Map<HabitualMode, Double> utilities = new HashMap<>();

        if (person.getOccupation() != Occupation.STUDENT && person.getOccupation() != Occupation.EMPLOYED) {
            person.setHabitualMode(HabitualMode.UNKNOWN);

            return;
        }
        for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
            utilities.put(habitualMode, calculateUtilityForThisMode(habitualMode, person));
        }

        final double utilityAutoD = utilities.get(HabitualMode.CAR_DRIVER);
        final double utilityAutoP = utilities.get(HabitualMode.CAR_PASSENGER);
        final double utilityPT = utilities.get(HabitualMode.PT);
        final double utilityBicycle = utilities.get(HabitualMode.BIKE);
        final double utilityWalk = utilities.get(HabitualMode.WALK);

        final Double nestingCoefficientAutoModes = coefficients.get(HabitualMode.CAR_DRIVER).get("nestingCoefficient");

        double expsumNestAuto = Math.exp(nestingCoefficientAutoModes * Math.log(Math.exp(utilityAutoD / nestingCoefficientAutoModes) +
                Math.exp(utilityAutoP / nestingCoefficientAutoModes)));

        double expsumTopLevel =
                expsumNestAuto +
                        Math.exp(utilityBicycle) +
                        Math.exp(utilityPT) +
                        Math.exp(utilityWalk);

        double probabilityAutoD;
        double probabilityAutoP;
        if (expsumNestAuto > 0) {
            probabilityAutoD =
                    (expsumNestAuto / expsumTopLevel) * Math.exp(utilityAutoD) / (Math.exp(utilityAutoD) + Math.exp(utilityAutoP));
            probabilityAutoP =
                    (expsumNestAuto / expsumTopLevel) * Math.exp(utilityAutoP) / (Math.exp(utilityAutoD) + Math.exp(utilityAutoP));
        } else {
            probabilityAutoD = 0.0;
            probabilityAutoP = 0.0;
        }

        double probabilityBike = Math.exp(utilityBicycle) / expsumTopLevel;
        double probabilityWalk = Math.exp(utilityWalk) / expsumTopLevel;
        double probabilityPT = Math.exp(utilityPT) / expsumTopLevel;

        EnumMap<HabitualMode, Double> probabilities = new EnumMap<>(HabitualMode.class);
        probabilities.put(HabitualMode.CAR_DRIVER, probabilityAutoD);
        probabilities.put(HabitualMode.CAR_PASSENGER, probabilityAutoP);
        probabilities.put(HabitualMode.BIKE, probabilityBike);
        probabilities.put(HabitualMode.WALK, probabilityWalk);
        probabilities.put(HabitualMode.PT, probabilityPT);

        //found Nan when there is no transit!!
        probabilities.replaceAll((mode, probability) ->
                probability.isNaN() ? 0 : probability);

        double sum = 0;
        for (double probability : probabilities.values()) {
            sum += probability;
        }

        if (sum > 0) {
            final HabitualMode select = MitoUtil.select(probabilities, AbitUtils.getRandomObject());
            person.setHabitualMode(select);
        } else {
            logger.error("Negative probabilities for person " + person.getId() + "'s habitual mode");
            person.setHabitualMode(HabitualMode.UNKNOWN);
        }
    }

    private double calculateUtilityForThisMode(HabitualMode habitualMode, Person person) {

        Household household = person.getHousehold();
        double utility = 0.;

        utility += coefficients.get(habitualMode).get("(Intercept)");

/*        utility += household.getPersons().size() * coefficients.get(mode).get("hh.size");

        int numAdults = (int) household.getPersons().stream().filter(p -> p.getRelationship() != Relationship.child || p.getAge() >= 18).count();
        double numAutos = household.getNumberOfCars();
        double autosPerAdult = numAutos / numAdults;
        if (autosPerAdult > 1) {
            autosPerAdult = 1.0;
        }*/

        /*        utility += autosPerAdult * coefficients.get(mode).get("hh.autosPerAdult");*/

        RegioStaR2 regioStaR2 = dataSet.getZones().get(household.getLocation().getZoneId()).getRegioStaR2Type();
        if (regioStaR2.equals(RegioStaR2.URBAN)) {
            utility += coefficients.get(habitualMode).get("hh.urban");
        }

        if (person.getGender().equals(Gender.FEMALE)) {
            utility += coefficients.get(habitualMode).get("p.female");
        }

        if (person.isHasLicense()) {
            utility += coefficients.get(habitualMode).get("p.driversLicense");
        }

        if (person.hasBicycle()) {
            utility += coefficients.get(habitualMode).get("p.ownBicycle");
        }

        if (person.getOccupation().equals(Occupation.STUDENT)) {
            utility += coefficients.get(habitualMode).get("p.occupationStatus_Student");
        }


/*        final double SPEED_WALK_KMH = 4;
        final double SPEED_BICYCLE_KMH = 10;
        if (person.getOccupation().equals(Occupation.EMPLOYED)) {
            double travelTime;
            double travelDistanceAuto;
            if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                travelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.CAR_DRIVER, person.getJob().getStartTime_min());
            } else if (habitualMode == HabitualMode.PT) {
                double travelTime_bus = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.BUS, person.getJob().getStartTime_min());
                double travelTime_train = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAIN, person.getJob().getStartTime_min());
                double travelTime_metro = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAM_METRO, person.getJob().getStartTime_min());
                travelTime = Math.min(travelTime_bus, travelTime_metro);
                travelTime = Math.min(travelTime, travelTime_train);
            } else if (habitualMode == HabitualMode.BIKE) {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_BICYCLE_KMH) * 60;
            } else {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_WALK_KMH) * 60;
            }

            utility += travelTime * coefficients.get(habitualMode).get("travelTime");
        }

        if (person.getOccupation().equals(Occupation.STUDENT)) {

            double travelTime;
            double travelDistanceAuto;
            if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                travelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.CAR_DRIVER, person.getSchool().getStartTime_min());
            } else if (habitualMode == HabitualMode.PT) {
                double travelTime_bus = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.BUS, person.getJob().getStartTime_min());
                double travelTime_train = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAIN, person.getJob().getStartTime_min());
                double travelTime_metro = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAM_METRO, person.getJob().getStartTime_min());
                travelTime = Math.min(travelTime_bus, travelTime_metro);
                travelTime = Math.min(travelTime, travelTime_train);
            } else if (habitualMode == HabitualMode.BIKE) {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_BICYCLE_KMH) * 60;
            } else {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_WALK_KMH) * 60;
            }
            utility += travelTime * coefficients.get(habitualMode).get("travelTime");
        }*/
        //generalized costs
        double generalizedCost = calculateGeneralizedCosts(person, habitualMode);

        utility += generalizedCost * coefficients.get(habitualMode).get("gc");

        //Todo add the latest calibration factors to the utility calculation
        switch (person.getOccupation()) {
            case EMPLOYED:
                utility += coefficients.get(habitualMode).get("calibration_employed");
            case STUDENT:
                utility += coefficients.get(habitualMode).get("calibration_student");
            case TODDLER:
                utility += coefficients.get(habitualMode).get("calibration_toddler");
            case RETIREE:
                utility += coefficients.get(habitualMode).get("calibration_retiree");
            case UNEMPLOYED:
                utility += coefficients.get(habitualMode).get("calibration_unemployed");
        }

        //Todo add updated calibration factor to the utility calculation, starting from 0
        if (runCalibration) {
            utility += updatedCalibrationFactors.get(person.getOccupation()).get(habitualMode);
        }
        return utility;
    }

    public void updateCalibrationFactor(Map<Occupation, Map<HabitualMode, Double>> newCalibrationFactors) {
        for (Occupation occupation : Occupation.values()) {

            for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
                double calibrationFactorFromLastIteration = this.updatedCalibrationFactors.get(occupation).get(habitualMode);
                double updatedCalibrationFactor = newCalibrationFactors.get(occupation).get(habitualMode) + calibrationFactorFromLastIteration;
                this.updatedCalibrationFactors.get(occupation).replace(habitualMode, updatedCalibrationFactor);
                logger.info("Calibration factor for " + occupation + "\t" + "and " + habitualMode + "\t" + ": " + updatedCalibrationFactor);

            }
        }
    }

    public Map<HabitualMode, Map<String, Double>> obtainCoefficientsTable() {

        double originalCalibrationFactor = 0.0;
        double updatedCalibrationFactor = 0.0;
        double latestCalibrationFactor = 0.0;

        for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
            for (Occupation occupation : Occupation.values()) {
                switch (occupation) {
                    case EMPLOYED:
                        originalCalibrationFactor = this.coefficients.get(habitualMode).get("calibration_employed");
                        updatedCalibrationFactor = updatedCalibrationFactors.get(occupation).get(habitualMode);
                        latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                        coefficients.get(habitualMode).replace("calibration_employed", latestCalibrationFactor);
                        break;
                    case STUDENT:
                        originalCalibrationFactor = this.coefficients.get(habitualMode).get("calibration_student");
                        updatedCalibrationFactor = updatedCalibrationFactors.get(occupation).get(habitualMode);
                        latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                        this.coefficients.get(habitualMode).replace("calibration_student", latestCalibrationFactor);
                    case TODDLER:
                        originalCalibrationFactor = this.coefficients.get(habitualMode).get("calibration_toddler");
                        updatedCalibrationFactor = updatedCalibrationFactors.get(occupation).get(habitualMode);
                        latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                        this.coefficients.get(habitualMode).replace("calibration_toddler", latestCalibrationFactor);
                    case RETIREE:
                        originalCalibrationFactor = this.coefficients.get(habitualMode).get("calibration_retiree");
                        updatedCalibrationFactor = updatedCalibrationFactors.get(occupation).get(habitualMode);
                        latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                        this.coefficients.get(habitualMode).replace("calibration_retiree", latestCalibrationFactor);
                    case UNEMPLOYED:
                        originalCalibrationFactor = this.coefficients.get(habitualMode).get("calibration_unemployed");
                        updatedCalibrationFactor = updatedCalibrationFactors.get(occupation).get(habitualMode);
                        latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                        this.coefficients.get(habitualMode).replace("calibration_unemployed", latestCalibrationFactor);
                }
            }
        }
        return this.coefficients;
    }

    //calculates generalized costs
    public Double calculateGeneralizedCosts(Person person, HabitualMode habitualMode) {
        final double SPEED_WALK_KMH = 4;
        final double SPEED_BICYCLE_KMH = 10;
        final double fuelCostEurosPerKm = 0.065;
        final double transitFareEurosPerKm = 0.12;
        double travelTime = 0;
        double travelDistanceAuto = 0;
        if (person.getOccupation().equals(Occupation.EMPLOYED)) {
            travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
            if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                travelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.CAR_DRIVER, person.getJob().getStartTime_min());
            } else if (habitualMode == HabitualMode.PT) {
                double travelTime_bus = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.BUS, person.getJob().getStartTime_min());
                double travelTime_train = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAIN, person.getJob().getStartTime_min());
                double travelTime_metro = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.TRAM_METRO, person.getJob().getStartTime_min());
                travelTime = Math.min(travelTime_bus, travelTime_metro);
                travelTime = Math.min(travelTime, travelTime_train);
            } else if (habitualMode == HabitualMode.BIKE) {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_BICYCLE_KMH) * 60;
            } else {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_WALK_KMH) * 60;
            }

        }

        if (person.getOccupation().equals(Occupation.STUDENT)) {
            travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
            if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                travelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.CAR_DRIVER, person.getSchool().getStartTime_min());
            } else if (habitualMode == HabitualMode.PT) {
                double travelTime_bus = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.BUS, person.getSchool().getStartTime_min());
                double travelTime_train = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.TRAIN, person.getSchool().getStartTime_min());
                double travelTime_metro = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.TRAM_METRO, person.getSchool().getStartTime_min());
                travelTime = Math.min(travelTime_bus, travelTime_metro);
                travelTime = Math.min(travelTime, travelTime_train);
            } else if (habitualMode == HabitualMode.BIKE) {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_BICYCLE_KMH) * 60;
            } else {
                travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
                travelTime = (travelDistanceAuto / 1000. / SPEED_WALK_KMH) * 60;
            }
        }


        travelDistanceAuto = travelDistanceAuto / 1000.;

        double generalizedCost = 0;

        double monthlyIncome_EUR = person.getHousehold().getPersons().stream().mapToInt(Person::getMonthlyIncome_eur).sum();

        //todo. Add VOT table with the coefficients and rename

        if (habitualMode == HabitualMode.BIKE || habitualMode == HabitualMode.WALK) {
            generalizedCost = travelTime;
        } else {
            if (monthlyIncome_EUR <= 1500) {
                if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                    generalizedCost = travelTime + (travelDistanceAuto * fuelCostEurosPerKm) / coefficients.get(habitualMode).get("vot_less_or_equal_income_4");
                } else if (habitualMode == HabitualMode.PT) {
                    generalizedCost = travelTime + (travelDistanceAuto * transitFareEurosPerKm) / coefficients.get(habitualMode).get("vot_less_or_equal_income_4");
                }
            } else if (monthlyIncome_EUR <= 5600) {
                if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                    generalizedCost = travelTime + (travelDistanceAuto * fuelCostEurosPerKm) / coefficients.get(habitualMode).get("vot_income_5_to_10");
                } else if (habitualMode == HabitualMode.PT) {
                    generalizedCost = travelTime + (travelDistanceAuto * transitFareEurosPerKm) / coefficients.get(habitualMode).get("vot_income_5_to_10");
                }
            } else {
                if (habitualMode == HabitualMode.CAR_DRIVER || habitualMode == HabitualMode.CAR_PASSENGER) {
                    generalizedCost = travelTime + (travelDistanceAuto * fuelCostEurosPerKm) / coefficients.get(habitualMode).get("vot_income_greater_10");
                } else if (habitualMode == HabitualMode.PT) {
                    generalizedCost = travelTime + (travelDistanceAuto * transitFareEurosPerKm) / coefficients.get(habitualMode).get("vot_income_greater_10");
                }
            }
        }

        return generalizedCost;
    }

}
