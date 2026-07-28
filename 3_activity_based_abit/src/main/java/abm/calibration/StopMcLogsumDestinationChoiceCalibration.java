package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.properties.AbitResources;
import abm.scenarios.lowEmissionZones.models.destinationChoice.McLogsumBasedDestinationChoiceModel;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class StopMcLogsumDestinationChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(StopMcLogsumDestinationChoiceCalibration.class);
    private static final int MAX_ITERATION = 100; //2_000_000;
    private static final double TERMINATION_THRESHOLD_AVERAGE_DISTANCE = 1.00;
    private static final double TERMINATION_THRESHOLD_0_2_KM = 0.05;
    String inputFolder = AbitResources.instance.getString("destination.choice.stop.act.logsum.output");
    DataSet dataSet;
    Map<Purpose, Double> objectiveStopDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Double> simulatedStopDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> objectiveStopDestinationDistBins = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> simulatedStopDestinationDistBins = new HashMap<>();
    Map<Purpose, Integer> numberOfAct = new HashMap<>();
    Map<Purpose, Map<String, Double>> calibrationFactors = new HashMap<>();
    private McLogsumBasedDestinationChoiceModel destinationChoiceModel;

    public StopMcLogsumDestinationChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() throws FileNotFoundException {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateMainDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.main.mcLogsum.destination.calibration"));
        boolean calibrateStopDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.stop.mcLogsum.destination.calibration"));
        destinationChoiceModel = new McLogsumBasedDestinationChoiceModel(dataSet, calibrateMainDestinationChoice, calibrateStopDestinationChoice);
        //Todo: initialize all the data containers that might be needed for calibration
        for (Purpose purpose : Purpose.getAllPurposes()) {
            calibrationFactors.putIfAbsent(purpose, new HashMap<>());
            objectiveStopDestinationAverageDistance_km.put(purpose, 0.0);
            simulatedStopDestinationAverageDistance_km.put(purpose, 0.0);
            objectiveStopDestinationDistBins.put(purpose, new HashMap<>());
            simulatedStopDestinationDistBins.put(purpose, new HashMap<>());
            numberOfAct.put(purpose, 0);
            calibrationFactors.get(purpose).put("ALPHA_calibration", 0.0);
            calibrationFactors.get(purpose).put("BETA_calibration", 0.0);
            calibrationFactors.get(purpose).put("distanceUtility", 0.0);
            for (int i = 0; i <= 20; i += 1) {
                objectiveStopDestinationDistBins.get(purpose).put(i, 0.0);
                simulatedStopDestinationDistBins.get(purpose).put(i, 0.0);
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
    public void run() throws FileNotFoundException {
        logger.info("Start calibrating the logsum stop destination choice model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;
            double maxDifferenceDistanceBin = 0.0;
            logger.info("Iteration: " + iteration);

            // Caliobrating beta
//            for (Purpose purpose : Purpose.getAllPurposes()) {
//                double differenceAverageDistance;
//                double factor = (simulatedStopDestinationAverageDistance_km.get(purpose) / objectiveStopDestinationAverageDistance_km.get(purpose));
//                factor = Math.max(factor, 0.85);
//                factor = Math.min(factor, 1.25);
//                differenceAverageDistance = Math.abs(objectiveStopDestinationAverageDistance_km.get(purpose) - simulatedStopDestinationAverageDistance_km.get(purpose));
//                calibrationFactors.get(purpose).replace("BETA_calibration", factor);
//                logger.info("Stop destination choice for" + purpose + "\t" + "average distance: " + simulatedStopDestinationAverageDistance_km.get(purpose));
//                if (differenceAverageDistance > maxDifference) {
//                    maxDifference = differenceAverageDistance;
//                }
//            }
//            if (maxDifference <= TERMINATION_THRESHOLD_AVERAGE_DISTANCE) {
//                break;
//            }
//            destinationChoiceModel.updateBetaCalibrationFactorsStop(calibrationFactors);
//            destinationChoiceModel.updateStopDestinationProbability();

            //Calibrate short distance < 2km
            for (Purpose purpose : Purpose.getAllPurposes()) {
                double diff_0_2_km = objectiveStopDestinationDistBins.get(purpose).get(0) - simulatedStopDestinationDistBins.get(purpose).get(0);
                double factor =  objectiveStopDestinationDistBins.get(purpose).get(0)/  simulatedStopDestinationDistBins.get(purpose).get(0);
                factor = Math.max(factor, 0.75);
                factor = Math.min(factor, 1.5);

                calibrationFactors.get(purpose).replace("distanceUtility", factor);

                logger.info("Main destination choice for" + purpose + "\t" + "difference of 0-2 km: " + diff_0_2_km);

                double differenceAverageDistance = Math.abs(objectiveStopDestinationAverageDistance_km.get(purpose) - simulatedStopDestinationAverageDistance_km.get(purpose));

                logger.info("Main destination choice for" + purpose + "\t" + "average distance: " + simulatedStopDestinationAverageDistance_km.get(purpose));

                if (!purpose.equals(Purpose.EDUCATION)) {
                    if (Math.abs(diff_0_2_km) > maxDifferenceDistanceBin) {
                        maxDifferenceDistanceBin = Math.abs(diff_0_2_km);
                    }
                    if (Math.abs(differenceAverageDistance) > maxDifference) {
                        maxDifference = differenceAverageDistance;
                    }
                }


            }
            if (maxDifferenceDistanceBin <= TERMINATION_THRESHOLD_0_2_KM && maxDifference <= TERMINATION_THRESHOLD_AVERAGE_DISTANCE) {
                break;
            }
            destinationChoiceModel.updateShortDistanceDisUtilityCalibrationFactorsStop(calibrationFactors);
            destinationChoiceModel.updateStopDestinationProbability();

            List<Household> simulatedHouseholds = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());
            simulatedHouseholds.parallelStream().forEach(household -> household.getPersons().forEach(person -> {
                for (Tour tour : person.getPlan().getTours().values()) {
                    for (Activity activity : tour.getActivities().values()) {
                        if (!activity.equals(tour.getMainActivity())) {
                            destinationChoiceModel.selectStopDestination(person, tour, activity);
                            break;
                        }
                    }
                }
            }));
            summarizeSimulatedResult();
        }
        logger.info("Finished the calibration of stop destination choice.");
        //Todo: obtain the updated coefficients + calibration factors
        Map<Purpose, Map<String, Double>> finalCoefficientsTableStop = destinationChoiceModel.obtainCoefficientsTableStop();
        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTableStop);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }
    }

    private void readObjectiveValues() {
        //todo add objective average distance
        objectiveStopDestinationAverageDistance_km.put(Purpose.WORK, 4.0565034873952674);
        objectiveStopDestinationAverageDistance_km.put(Purpose.EDUCATION, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.ACCOMPANY, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.SHOPPING, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.OTHER, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.RECREATION, 3.6220093126038324);

        objectiveStopDestinationDistBins.get(Purpose.WORK).put(0, 0.3773);
        objectiveStopDestinationDistBins.get(Purpose.EDUCATION).put(0, 0.4791);
        objectiveStopDestinationDistBins.get(Purpose.ACCOMPANY).put(0, 0.3793);
        objectiveStopDestinationDistBins.get(Purpose.SHOPPING).put(0, 0.4262);
        objectiveStopDestinationDistBins.get(Purpose.OTHER).put(0, 0.4208);
        objectiveStopDestinationDistBins.get(Purpose.RECREATION).put(0, 0.3561);
    }

    private void summarizeSimulatedResult() {

        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedStopDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);
            for (int i = 0; i <= 20; i += 1) {
                simulatedStopDestinationDistBins.get(purpose).put(i, 0.0);
            }
        }

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    for (Tour tour : person.getPlan().getTours().values()) {
                        Purpose tourPurpose = tour.getMainActivity().getPurpose();
                        for (Activity activity : tour.getActivities().values()) {
                            if (!activity.equals(tour.getMainActivity())) {
                                double distanceInMeters;
                                if (tourPurpose.equals(Purpose.WORK)) {
                                    distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(household.getLocation(), activity.getLocation(), Mode.UNKNOWN, 0.);
                                } else {
                                    distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(tour.getMainActivity().getLocation(), activity.getLocation(), Mode.UNKNOWN, 0.);
                                }
                                double distanceInKm = distanceInMeters / 1000;
                                int distanceInKmRounded = (int) Math.floor(distanceInKm);
                                if (distanceInKmRounded > 20) {
                                    distanceInKmRounded = 20;
                                }
                                //here actually is the total distance for each purpose
                                simulatedStopDestinationAverageDistance_km.put(tourPurpose, simulatedStopDestinationAverageDistance_km.get(tourPurpose) + distanceInKm);
                                simulatedStopDestinationDistBins.get(tourPurpose).put(distanceInKmRounded, simulatedStopDestinationDistBins.get(tourPurpose).get(distanceInKmRounded) + 1);
                                numberOfAct.put(tourPurpose, numberOfAct.get(tourPurpose) + 1);
                                break;
                            }
                        }
                    }
                }
            }
        }
        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedStopDestinationAverageDistance_km.put(purpose, simulatedStopDestinationAverageDistance_km.get(purpose) / numberOfAct.get(purpose));
            simulatedStopDestinationDistBins.get(purpose).forEach((distance, count) -> simulatedStopDestinationDistBins.get(purpose).put(distance, count / (double) numberOfAct.get(purpose)));
        }
    }

    private void printFinalCoefficientsTable(Map<Purpose, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing stop destination choice coefficient + calibration factors: " + inputFolder);
        PrintWriter pw = new PrintWriter(inputFolder);
        StringBuilder header = new StringBuilder("variable");
        for (Purpose purpose : Purpose.getAllPurposes()) {
            header.append(",");
            header.append(purpose);
        }
        pw.println(header);
        for (String variableNames : finalCoefficientsTable.get(Purpose.WORK).keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            for (Purpose purpose : Purpose.getAllPurposes()) {
                line.append(",");
                line.append(finalCoefficientsTable.get(purpose).get(variableNames));
            }
            pw.println(line);
        }
        pw.close();

        PrintWriter pw2 = new PrintWriter("input/models/destinationChoice/distDistribution_stop_logsum.csv");
        pw2.println("purpose, alpha, beta, distance, share");
        for (Purpose purpose : Purpose.getAllPurposes()) {
            for (int i = 0; i <= 20; i += 1) {
                String line2 = purpose.toString() + "," +
                        finalCoefficientsTable.get(purpose).get("ALPHA") +
                        "," +
                        finalCoefficientsTable.get(purpose).get("BETA") * finalCoefficientsTable.get(purpose).get("BETA_calibration") +
                        "," +
                        i +
                        "," +
                        simulatedStopDestinationDistBins.get(purpose).get(i);
                pw2.println(line2);
            }
        }
        pw2.close();
    }
}

