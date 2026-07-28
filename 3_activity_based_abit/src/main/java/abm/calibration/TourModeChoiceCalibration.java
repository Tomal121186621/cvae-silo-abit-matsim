package abm.calibration;

import abm.data.DataSet;
import abm.data.geo.Location;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.vehicle.Car;
import abm.io.input.CalibrationZoneToRegionTypeReader;
import abm.models.modeChoice.NestedLogitTourModeChoiceModel;
import abm.properties.AbitResources;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.time.DayOfWeek;
import java.util.*;
import java.util.stream.Collectors;

import static abm.io.input.CalibrationZoneToRegionTypeReader.getRegionForZone;

public class TourModeChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(TourModeChoiceCalibration.class);

    private static final int MAX_ITERATION = 100;
    private static final double TERMINATION_THRESHOLD = 0.02;

    double stepSize = 1.00;
    String inputFolder = AbitResources.instance.getString("tour.mode.coef.output");
    DataSet dataSet;
    Map<String, Map<Purpose, Map<DayOfWeek, Map<Mode, Double>>>> objectiveTourModeShare = new HashMap<>();
    Map<String,Map<Purpose, Map<DayOfWeek, Map<Mode, Integer>>>> simulatedTourModeCount = new HashMap<>();
    Map<String,Map<Purpose, Map<DayOfWeek, Map<Mode, Double>>>> simulatedTourModeShare = new HashMap<>();
    Map<String,Map<Purpose, Map<DayOfWeek, Map<Mode, Double>>>> calibrationFactors = new HashMap<>();
    private NestedLogitTourModeChoiceModel tourModeChoiceModelCalibration;
    //private CalibrationZoneToRegionTypeReader zoneToRegionMap;

    List<String> regions = new ArrayList<>();
    {regions.add("muc");
    regions.add("nonMuc");}


    public TourModeChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;

    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateTourModeChoice = Boolean.parseBoolean(AbitResources.instance.getString("tour.mode.calibration"));
        tourModeChoiceModelCalibration = new NestedLogitTourModeChoiceModel(dataSet, calibrateTourModeChoice);

        //Todo: initialize all the data containers that might be needed for calibration
        //tourmodechoice

        for (String region : regions) {
            objectiveTourModeShare.putIfAbsent(region, new HashMap<>());
            simulatedTourModeCount.putIfAbsent(region, new HashMap<>());
            simulatedTourModeShare.putIfAbsent(region, new HashMap<>());
            calibrationFactors.putIfAbsent(region, new HashMap<>());
            for (Purpose purpose : Purpose.getSortedPurposes()) {
                objectiveTourModeShare.get(region).putIfAbsent(purpose, new HashMap<>());
                simulatedTourModeCount.get(region).putIfAbsent(purpose, new HashMap<>());
                simulatedTourModeShare.get(region).putIfAbsent(purpose, new HashMap<>());
                calibrationFactors.get(region).putIfAbsent(purpose, new HashMap<>());
                for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                    objectiveTourModeShare.get(region).get(purpose).putIfAbsent(dayOfWeek, new HashMap<>());
                    simulatedTourModeCount.get(region).get(purpose).putIfAbsent(dayOfWeek, new HashMap<>());
                    simulatedTourModeShare.get(region).get(purpose).putIfAbsent(dayOfWeek, new HashMap<>());
                    calibrationFactors.get(region).get(purpose).putIfAbsent(dayOfWeek, new HashMap<>());
                    for (Mode mode : Mode.values()) {
                        objectiveTourModeShare.get(region).get(purpose).get(dayOfWeek).putIfAbsent(mode, 0.0);
                        simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).putIfAbsent(mode, 0);
                        simulatedTourModeShare.get(region).get(purpose).get(dayOfWeek).putIfAbsent(mode, 0.0);
                        calibrationFactors.get(region).get(purpose).get(dayOfWeek).putIfAbsent(mode, 0.0);
                    }
                }
            }
        }
    }

    @Override
    public void load() {
        //Todo: read objective values
        readObjectiveValues();

        //Todo: consider having the result summarization in the statistics writer
        summarizeSimulatedResult();
    }

    @Override
    public void run() {

        logger.info("Start calibrating the habitual mode choice model......");
        List<Household> simulatedHouseholds = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());

        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            logger.info("Iteration......" + iteration);
            double maxDifference = 0.0;

            //Todo summarize share difference and share
            for (String region : regions) {
                for (Purpose purpose : Purpose.getAllPurposes()) {
                    for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                        for (Mode mode : Mode.getModes()) {
                            double observedShare = objectiveTourModeShare.get(region).get(purpose).get(dayOfWeek).get(mode);
                            double simulatedShare = simulatedTourModeShare.get(region).get(purpose).get(dayOfWeek).get(mode);
                            double difference = observedShare - simulatedShare;
                            double factor = stepSize * (observedShare - simulatedShare);
                            if (mode.equals(Mode.CAR_DRIVER)) {
                                factor = 0.00;
                            }
                            if (dayOfWeek.equals(DayOfWeek.SUNDAY) && purpose.equals(Purpose.SHOPPING)) {
                                factor = 0.00;
                            }
                            calibrationFactors.get(region).get(purpose).get(dayOfWeek).replace(mode, factor);

                            if (dayOfWeek.equals(DayOfWeek.MONDAY) || dayOfWeek.equals(DayOfWeek.SATURDAY)){
                                logger.info("Tour mode choice model for " + purpose.toString() + "\t" + dayOfWeek.toString() + "\t" + " and " + mode.toString() + "\t" + region  + "\t" +
                                        "difference: " + difference);
                            }



                            if (Math.abs(difference) > maxDifference) {
                                maxDifference = Math.abs(difference);
                            }
                        }
                    }
                }
            }

            tourModeChoiceModelCalibration.updateCalibrationFactor(calibrationFactors);

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            } else {
                logger.info("MAX Diff: " + maxDifference);
            }

            simulatedHouseholds.parallelStream().forEach(household -> {
                household.getVehicles().parallelStream().forEach(vehicle -> {
                    ((Car) vehicle).getBlockedTimeOfWeek().resetCarBlockedTimeOfWeekLinkedList();
                });
            });

            for (Household household : simulatedHouseholds){
                if (household.getNumberOfCars() > 0){
                    for (Purpose purpose : Purpose.getSortedPurposes()) {
                        if (purpose.equals(Purpose.WORK)) {
                            //Step 1: loop over all workers in the household, check car and transit travel time ratio
                            // car/pt ratio the smaller (more poor pt accessibility compared to car), then higher preference to use car
                            List<Person> workers = household.getPersons().stream().filter(pp -> pp.hasWorkActivity()).collect(Collectors.toList());
                            Map<Person, Double> carUsePreference = new HashMap<>();
                            for (Person person : workers) {
                                Location jobLocation;
                                double startTime;
                                if (person.getJob() != null) {
                                    jobLocation = person.getJob().getLocation();
                                    startTime = person.getJob().getStartTime_min();
                                } else {
                                    //job location for non-employed person but has a work tour, e.g. student go for interview or internship
                                    Activity workActivity = person.getPlan().getTours().values().stream().filter(tour -> tour.getMainActivity().getPurpose().equals(Purpose.WORK)).collect(Collectors.toList()).get(0).getMainActivity();
                                    jobLocation = workActivity.getLocation();
                                    startTime = workActivity.getStartTime_min();
                                }

                                int carTravelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), jobLocation, Mode.CAR_DRIVER, startTime);
                                int transitTravelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), jobLocation, Mode.TRAIN, startTime);
                                double carPtRatio = carTravelTime / (double) transitTravelTime;
                                carUsePreference.put(person, carPtRatio);
                            }

                            List<Map.Entry<Person, Double>> sortedPreference = new ArrayList<>(carUsePreference.entrySet());
                            Collections.sort(sortedPreference, Map.Entry.comparingByValue());

                            //Step 2: check availability and choose mode for Work tours by the order of preference
                            for (Map.Entry<Person, Double> entry : sortedPreference) {
                                entry.getKey().getPlan().getTours().values().forEach(tour -> {
                                    if (tour.getMainActivity().getPurpose().equals(Purpose.WORK)) {
                                        tourModeChoiceModelCalibration.checkCarAvailabilityAndChooseMode(household, entry.getKey(), tour, Purpose.WORK);
                                    }
                                });
                            }
                        } else {
                            //check availability and choose mode for other tours by the order of (education > accompany > other > shopping > recreational)
                            for (Person person : household.getPersons()) {
                                person.getPlan().getTours().values().forEach(tour -> {
                                    if (tour.getMainActivity().getPurpose().equals(purpose)) {
                                        tourModeChoiceModelCalibration.checkCarAvailabilityAndChooseMode(household, person, tour, purpose);
                                    }
                                });
                            }
                        }
                    }
                }else{
                    for (Person person : household.getPersons()) {
                        person.getPlan().getTours().values().forEach(tour -> {
                            tourModeChoiceModelCalibration.chooseMode(person, tour, tour.getMainActivity().getPurpose(), Boolean.FALSE);
                        });
                    }
                }
            }

            summarizeSimulatedResult();

        }

        logger.info("Finished the calibration of habitual mode choice model.");

        //Todo: obtain the updated coefficients + calibration factors
        Map<Purpose, Map<Mode, Map<String, Double>>> finalCoefficientsTable = tourModeChoiceModelCalibration.obtainCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTable);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    //WORK; EDUCATION; ACCOMPANY; OTHER; SHOP; RECR
    private void readObjectiveValues() {
        //map for muc region
        Map<Mode, Double> weekdayValuesMucWork = Map.of(
                Mode.CAR_DRIVER, 0.38, Mode.CAR_PASSENGER, 0.01, Mode.BUS, 0.02,
                Mode.TRAIN, 0.18, Mode.TRAM_METRO, 0.26, Mode.BIKE, 0.12, Mode.WALK, 0.02);
        Map<Mode, Double> weekendValuesMucWork = Map.of(
                Mode.CAR_DRIVER, 0.47, Mode.CAR_PASSENGER, 0.01, Mode.BUS, 0.03,
                Mode.TRAIN, 0.11, Mode.TRAM_METRO, 0.25, Mode.BIKE, 0.11, Mode.WALK, 0.02);
        Map<Mode, Double> weekdayValuesMucEducation = Map.of(
                Mode.CAR_DRIVER, 0.03, Mode.CAR_PASSENGER, 0.17, Mode.BUS, 0.10,
                Mode.TRAIN, 0.13, Mode.TRAM_METRO, 0.24, Mode.BIKE, 0.21, Mode.WALK, 0.12);
        Map<Mode, Double> weekendValuesMucEducation = Map.of(
                Mode.CAR_DRIVER, 0.09, Mode.CAR_PASSENGER, 0.12, Mode.BUS, 0.04,
                Mode.TRAIN, 0.22, Mode.TRAM_METRO, 0.35, Mode.BIKE, 0.13, Mode.WALK, 0.05);
        Map<Mode, Double> weekdayValuesMucAccompany = Map.of(
                Mode.CAR_DRIVER, 0.46, Mode.CAR_PASSENGER, 0.16, Mode.BUS, 0.02,
                Mode.TRAIN, 0.04, Mode.TRAM_METRO, 0.10, Mode.BIKE, 0.10, Mode.WALK, 0.12);
        Map<Mode, Double> weekendValuesMucAccompany = Map.of(
                Mode.CAR_DRIVER, 0.30, Mode.CAR_PASSENGER, 0.24, Mode.BUS, 0.01,
                Mode.TRAIN, 0.04, Mode.TRAM_METRO, 0.18, Mode.BIKE, 0.06, Mode.WALK, 0.16);
        Map<Mode, Double> weekdayValuesMucShop = Map.of(
                Mode.CAR_DRIVER, 0.31, Mode.CAR_PASSENGER, 0.09, Mode.BUS, 0.04,
                Mode.TRAIN, 0.06, Mode.TRAM_METRO, 0.13, Mode.BIKE, 0.12, Mode.WALK, 0.25);
        Map<Mode, Double> weekendValuesMucShop = Map.of(
                Mode.CAR_DRIVER, 0.31, Mode.CAR_PASSENGER, 0.13, Mode.BUS, 0.03,
                Mode.TRAIN, 0.04, Mode.TRAM_METRO, 0.11, Mode.BIKE, 0.14, Mode.WALK, 0.23);
        Map<Mode, Double> weekdayValuesMucOther = Map.of(
                Mode.CAR_DRIVER, 0.28, Mode.CAR_PASSENGER, 0.12, Mode.BUS, 0.05,
                Mode.TRAIN, 0.09, Mode.TRAM_METRO, 0.21, Mode.BIKE, 0.09, Mode.WALK, 0.16);
        Map<Mode, Double> weekendValuesMucOther = Map.of(
                Mode.CAR_DRIVER, 0.30, Mode.CAR_PASSENGER, 0.23, Mode.BUS, 0.03,
                Mode.TRAIN, 0.07, Mode.TRAM_METRO, 0.13, Mode.BIKE, 0.08, Mode.WALK, 0.17);
        Map<Mode, Double> weekdayValuesMucRecreation = Map.of(
                Mode.CAR_DRIVER, 0.20, Mode.CAR_PASSENGER, 0.13, Mode.BUS, 0.04,
                Mode.TRAIN, 0.08, Mode.TRAM_METRO, 0.17, Mode.BIKE, 0.17, Mode.WALK, 0.22);
        Map<Mode, Double> weekendValuesMucRecreation = Map.of(
                Mode.CAR_DRIVER, 0.22, Mode.CAR_PASSENGER, 0.19, Mode.BUS, 0.03,
                Mode.TRAIN, 0.08, Mode.TRAM_METRO, 0.16, Mode.BIKE, 0.13, Mode.WALK, 0.20);
        // maps for nonmuc region
        Map<Mode, Double> weekdayValuesNonmucWork = Map.of(
                Mode.CAR_DRIVER, 0.68, Mode.CAR_PASSENGER, 0.03, Mode.BUS, 0.02,
                Mode.TRAIN, 0.13, Mode.TRAM_METRO, 0.03, Mode.BIKE, 0.08, Mode.WALK, 0.03);
        Map<Mode, Double> weekendValuesNonmucWork = Map.of(
                Mode.CAR_DRIVER, 0.68, Mode.CAR_PASSENGER, 0.13, Mode.BUS, 0.02,
                Mode.TRAIN, 0.06, Mode.TRAM_METRO, 0.02, Mode.BIKE, 0.05, Mode.WALK, 0.05);
        Map<Mode, Double> weekdayValuesNonmucEducation = Map.of(
                Mode.CAR_DRIVER, 0.07, Mode.CAR_PASSENGER, 0.23, Mode.BUS, 0.25,
                Mode.TRAIN, 0.12, Mode.TRAM_METRO, 0.03, Mode.BIKE, 0.16, Mode.WALK, 0.12);
        Map<Mode, Double> weekendValuesNonmucEducation = Map.of(
                Mode.CAR_DRIVER, 0.19, Mode.CAR_PASSENGER, 0.07, Mode.BUS, 0.15,
                Mode.TRAIN, 0.28, Mode.TRAM_METRO, 0.05, Mode.BIKE, 0.15, Mode.WALK, 0.11);
        Map<Mode, Double> weekdayValuesNonmucAccompany = Map.of(
                Mode.CAR_DRIVER, 0.68, Mode.CAR_PASSENGER, 0.18, Mode.BUS, 0.02,
                Mode.TRAIN, 0.01, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.05, Mode.WALK, 0.05);
        Map<Mode, Double> weekendValuesNonmucAccompany = Map.of(
                Mode.CAR_DRIVER, 0.57, Mode.CAR_PASSENGER, 0.31, Mode.BUS, 0.01,
                Mode.TRAIN, 0.01, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.05, Mode.WALK, 0.04);
        Map<Mode, Double> weekdayValuesNonmucShop = Map.of(
                Mode.CAR_DRIVER, 0.56, Mode.CAR_PASSENGER, 0.14, Mode.BUS, 0.01,
                Mode.TRAIN, 0.02, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.13, Mode.WALK, 0.13);
        Map<Mode, Double> weekendValuesNonmucShop = Map.of(
                Mode.CAR_DRIVER, 0.54, Mode.CAR_PASSENGER, 0.19, Mode.BUS, 0.01,
                Mode.TRAIN, 0.02, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.14, Mode.WALK, 0.10);
        Map<Mode, Double> weekdayValuesNonmucOther = Map.of(
                Mode.CAR_DRIVER, 0.52, Mode.CAR_PASSENGER, 0.17, Mode.BUS, 0.03,
                Mode.TRAIN, 0.05, Mode.TRAM_METRO, 0.02, Mode.BIKE, 0.11, Mode.WALK, 0.11);
        Map<Mode, Double> weekendValuesNonmucOther = Map.of(
                Mode.CAR_DRIVER, 0.46, Mode.CAR_PASSENGER, 0.25, Mode.BUS, 0.01,
                Mode.TRAIN, 0.03, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.09, Mode.WALK, 0.15);
        Map<Mode, Double> weekdayValuesNonmucRecreation = Map.of(
                Mode.CAR_DRIVER, 0.33, Mode.CAR_PASSENGER, 0.22, Mode.BUS, 0.01,
                Mode.TRAIN, 0.03, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.17, Mode.WALK, 0.22);
        Map<Mode, Double> weekendValuesNonmucRecreation = Map.of(
                Mode.CAR_DRIVER, 0.35, Mode.CAR_PASSENGER, 0.27, Mode.BUS, 0.01,
                Mode.TRAIN, 0.03, Mode.TRAM_METRO, 0.01, Mode.BIKE, 0.12, Mode.WALK, 0.22);


        // Initialize the main map for all combinations
        objectiveTourModeShare = new HashMap<>();

        for (String region : List.of("muc", "nonMuc")) {
            Map<Purpose, Map<DayOfWeek, Map<Mode, Double>>> purposeMap = new HashMap<>();
            for (Purpose purpose : Purpose.values()) {
                Map<DayOfWeek, Map<Mode, Double>> dayMap = new EnumMap<>(DayOfWeek.class);
                for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                    Map<Mode, Double> values;
                    if (region.equals("muc")) {
                        switch (purpose) {
                            case WORK:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucWork : weekdayValuesMucWork;
                                break;
                            case EDUCATION:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucEducation : weekdayValuesMucEducation;
                                break;
                            case ACCOMPANY:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucAccompany : weekdayValuesMucAccompany;
                                break;
                            case SHOPPING:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucShop : weekdayValuesMucShop;
                                break;
                            case OTHER:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucOther : weekdayValuesMucOther;
                                break;
                            case RECREATION:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesMucRecreation : weekdayValuesMucRecreation;
                                break;
                            default:
                                values = new HashMap<>(); // Default empty map
                        }
                    } else {
                        switch (purpose) {
                            case WORK:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucWork : weekdayValuesNonmucWork;
                                break;
                            case EDUCATION:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucEducation : weekdayValuesNonmucEducation;
                                break;
                            case ACCOMPANY:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucAccompany : weekdayValuesNonmucAccompany;
                                break;
                            case SHOPPING:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucShop : weekdayValuesNonmucShop;
                                break;
                            case OTHER:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucOther : weekdayValuesNonmucOther;
                                break;
                            case RECREATION:
                                values = dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY ? weekendValuesNonmucRecreation : weekdayValuesNonmucRecreation;
                                break;
                            default:
                                values = new HashMap<>(); // Default empty map
                        }
                    }
                    dayMap.put(dayOfWeek, new HashMap<>(values));
                }
                purposeMap.put(purpose, dayMap);
            }
            objectiveTourModeShare.put(region, purposeMap);
        }
    }


    private void summarizeSimulatedResult() {
        for (String region : regions) {
            for (Purpose purpose : Purpose.getSortedPurposes()) {
                for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                    for (Mode mode : Mode.values()) {
                        simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).put(mode, 0);
                        simulatedTourModeShare.get(region).get(purpose).get(dayOfWeek).put(mode, 0.0);
                    }
                }
            }
        }

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    Plan plan = person.getPlan();
                    for (Tour tour : plan.getTours().values()) {
                        Purpose purpose = tour.getMainActivity().getPurpose();
                        DayOfWeek dayOfWeek = tour.getMainActivity().getDayOfWeek();
                        Mode mode = tour.getTourMode();
                        String region = getRegionForZone(tour.getActivities().get(tour.getActivities().firstKey()).
                                getLocation().getZoneId());

                        int count = simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).get(mode);
                        count = count + 1;
                        simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).replace(mode, count);

                    }

                }
            }
        }
        for (String region : regions) {
            for (Purpose purpose : Purpose.getSortedPurposes()) {
                for (Mode mode : Mode.getModes()) {

                    int cumulativeSumByMode_Weekday = 0;
                    int cumulativeSumByMode_Weekend = 0;
                    for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                        if (dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY) {
                            cumulativeSumByMode_Weekend = cumulativeSumByMode_Weekend + simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).get(mode);
                        } else {
                            cumulativeSumByMode_Weekday = cumulativeSumByMode_Weekday + simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).get(mode);
                        }
                    }

                    for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                        if (dayOfWeek == DayOfWeek.SATURDAY || dayOfWeek == DayOfWeek.SUNDAY) {
                            simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).replace(mode, cumulativeSumByMode_Weekend);
                        }else{
                            simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).replace(mode, cumulativeSumByMode_Weekday);
                        }
                    }

                }

                for (DayOfWeek dayOfWeek : DayOfWeek.values()) {
                    int cumulativeSum = 0;
                    for (Mode mode : Mode.getModes()) {
                        cumulativeSum = cumulativeSum + simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).get(mode);
                    }
                    for (Mode mode : Mode.getModes()) {
                        double share = (double) simulatedTourModeCount.get(region).get(purpose).get(dayOfWeek).get(mode) / cumulativeSum;
                        simulatedTourModeShare.get(region).get(purpose).get(dayOfWeek).replace(mode, share);
                    }
                }
            }
        }
    }

    private void printFinalCoefficientsTable(Map<Purpose, Map<Mode, Map<String, Double>>> finalCoefficientsTable) throws FileNotFoundException {

//        accompanyMode_nestedLogit.csv
//        shoppingMode_nestedLogit.csv
//        recreationMode_nestedLogit.csv
//        otherMode_nestedLogit.csv

        logger.info("Writing tour mode choice coefficient + calibration factors: " + inputFolder + "mandatoryMode_nestedLogit_calibrated.csv");
        PrintWriter pw = new PrintWriter(inputFolder + "mandatoryMode_nestedLogit_calibrated.csv");

        StringBuilder header = new StringBuilder("variable");
        for (Mode mode : Mode.getModes()) {
            header.append(",");
            header.append(mode);
        }
        pw.println(header);

        for (String variableNames : finalCoefficientsTable.get(Purpose.WORK).get(Mode.BUS).keySet()) {
            StringBuilder line = new StringBuilder(variableNames);

            if (variableNames.equals("calibration_education_monday_muc") || variableNames.equals("calibration_education_tuesday_muc") ||
                    variableNames.equals("calibration_education_wednesday_muc") || variableNames.equals("calibration_education_thursday_muc") ||
                    variableNames.equals("calibration_education_friday_muc") || variableNames.equals("calibration_education_saturday_muc") ||
                    variableNames.equals("calibration_education_sunday_muc")||variableNames.equals("calibration_education_monday_nonmuc") ||
                    variableNames.equals("calibration_education_tuesday_nonmuc") ||
                    variableNames.equals("calibration_education_wednesday_nonmuc") || variableNames.equals("calibration_education_thursday_nonmuc") ||
                    variableNames.equals("calibration_education_friday_nonmuc") || variableNames.equals("calibration_education_saturday_nonmuc") ||
                    variableNames.equals("calibration_education_sunday_nonmuc")) {


                for (Mode mode : Mode.getModes()) {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(Purpose.EDUCATION).get(mode).get(variableNames));
                }

            } else {
                for (Mode mode : Mode.getModes()) {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(Purpose.WORK).get(mode).get(variableNames));
                }
            }
            pw.println(line);
        }
        pw.close();

        //one for discretionary


        for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {

            logger.info("Writing tour mode choice coefficient + calibration factors: " + inputFolder + purpose + "Mode_nestedLogit_calibrated.csv");
            PrintWriter pww = new PrintWriter(inputFolder + purpose.toString().toLowerCase() + "Mode_nestedLogit_calibrated.csv");

            StringBuilder headerr = new StringBuilder("variable");
            for (Mode mode : Mode.getModes()) {
                headerr.append(",");
                headerr.append(mode);
            }
            pww.println(headerr);


            for (String variableNames : finalCoefficientsTable.get(Purpose.SHOPPING).get(Mode.BUS).keySet()) {
                StringBuilder line = new StringBuilder(variableNames);

                for (Mode mode : Mode.getModes()) {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(purpose).get(mode).get(variableNames));
                }

                pww.println(line);
            }
            pww.close();

        }

    }


}
