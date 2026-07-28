package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.properties.AbitResources;
import abm.scenarios.lowEmissionZones.models.destinationChoice.McLogsumBasedDestinationChoiceModel;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;
import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class MainMcLogsumDestinationChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(MainMcLogsumDestinationChoiceCalibration.class);
    private static final int MAX_ITERATION = 20;
    private static final double TERMINATION_THRESHOLD_AVG_DISTANCE = 1.5;
    private static final double TERMINATION_THRESHOLD_0_2_KM = 0.05;

    String inputFolder = AbitResources.instance.getString("destination.choice.main.act.logsum.output");
    DataSet dataSet;
    Map<Purpose, Double> objectiveMainDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Double> simulatedMainDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> objectiveMainDestinationDistBins = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> simulatedMainDestinationDistBins = new HashMap<>();
    Map<Purpose, Integer> numberOfAct = new HashMap<>();
    Map<Purpose, Map<String, Double>> calibrationFactors = new HashMap<>();
    private McLogsumBasedDestinationChoiceModel destinationChoiceModel;

    public MainMcLogsumDestinationChoiceCalibration(DataSet dataSet) {
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
            objectiveMainDestinationAverageDistance_km.put(purpose, .0);
            simulatedMainDestinationAverageDistance_km.put(purpose, .0);
            objectiveMainDestinationDistBins.put(purpose, new HashMap<>());
            simulatedMainDestinationDistBins.put(purpose, new HashMap<>());
            numberOfAct.put(purpose, 0);
            calibrationFactors.get(purpose).put("ALPHA_calibration", 0.0);
            calibrationFactors.get(purpose).put("BETA_calibration", 0.0);
            calibrationFactors.get(purpose).put("distanceUtility", 0.0);
            for (int i = 0; i <= 40; i += 2) {
                objectiveMainDestinationDistBins.get(purpose).put(i, 0.0);
                simulatedMainDestinationDistBins.get(purpose).put(i, 0.0);
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
        logger.info("Start calibrating the main logsum destination choice model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;
            double maxDifferenceDistanceBin = 0.0;
            logger.info("Iteration: " + iteration);

            // Caliobrating beta
//            for (Purpose purpose : Purpose.getAllPurposes()) {
//                double differenceAverageDistance;
//                double factor = (simulatedMainDestinationAverageDistance_km.get(purpose) / objectiveMainDestinationAverageDistance_km.get(purpose));
//                factor = Math.max(factor, 0.85);
//                factor = Math.min(factor, 1.25);
//                differenceAverageDistance = Math.abs(simulatedMainDestinationAverageDistance_km.get(purpose) - objectiveMainDestinationAverageDistance_km.get(purpose));
//                //todo calculate the difference between observed and simulated average distance
//                if (purpose.equals(Purpose.EDUCATION)) {
//                    calibrationFactors.get(purpose).replace("BETA_calibration", 1.0);
//                } else {
//                    calibrationFactors.get(purpose).replace("BETA_calibration", factor);
//                }
//                logger.info("Main destination choice for" + purpose + "\t" + "average distance: " + simulatedMainDestinationAverageDistance_km.get(purpose));
//                if (!purpose.equals(Purpose.WORK) && !purpose.equals(Purpose.EDUCATION)) {
//                    if (Math.abs(differenceAverageDistance) > maxDifference) {
//                        maxDifference = differenceAverageDistance;
//                    }
//                }
//            }
//            if (maxDifference <= TERMINATION_THRESHOLD_AVG_DISTANCE) {
//                break;
//            }
//            destinationChoiceModel.updateBetaCalibrationFactorsMain(calibrationFactors);
//            destinationChoiceModel.updateMainDestinationProbability();

            //Calibrate short distance < 2km
            for (Purpose purpose : Purpose.getAllPurposes()) {
                double diff_0_2_km = objectiveMainDestinationDistBins.get(purpose).get(0) - simulatedMainDestinationDistBins.get(purpose).get(0);
                double factor =  objectiveMainDestinationDistBins.get(purpose).get(0) /  simulatedMainDestinationDistBins.get(purpose).get(0);
                factor = Math.max(factor, 0.5);
                factor = Math.min(factor, 2);

                if (purpose.equals(Purpose.EDUCATION)) {
                    calibrationFactors.get(purpose).replace("distanceUtility", 1.0);
                    diff_0_2_km = 0.0;
                } else {
                    calibrationFactors.get(purpose).replace("distanceUtility", factor);
                }

                logger.info("Main destination choice for" + purpose + "\t" + "difference of 0-2 km: " + diff_0_2_km);

                double differenceAverageDistance = Math.abs(objectiveMainDestinationAverageDistance_km.get(purpose) - simulatedMainDestinationAverageDistance_km.get(purpose));

                logger.info("Main destination choice for" + purpose + "\t" + "average distance: " + simulatedMainDestinationAverageDistance_km.get(purpose));

                if (!purpose.equals(Purpose.EDUCATION)) {
                    if (Math.abs(diff_0_2_km) > maxDifferenceDistanceBin) {
                        maxDifferenceDistanceBin = Math.abs(diff_0_2_km);
                    }
                    if (Math.abs(differenceAverageDistance) > maxDifference) {
                        maxDifference = differenceAverageDistance;
                    }
                }


            }
            if (maxDifferenceDistanceBin <= TERMINATION_THRESHOLD_0_2_KM && maxDifference <= TERMINATION_THRESHOLD_AVG_DISTANCE) {

                break;
            }
            destinationChoiceModel.updateShortDistanceDisUtilityCalibrationFactorsMain(calibrationFactors);
            destinationChoiceModel.updateMainDestinationProbability();

            List<Household> simulatedHouseholds = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());
            simulatedHouseholds.parallelStream().forEach(household -> household.getPersons().forEach(person -> person.getPlan().getTours().forEach((tourIndex, tour) -> destinationChoiceModel.selectMainActivityDestination(person, tour.getMainActivity()))));
            summarizeSimulatedResult();

        }
        logger.info("Finished the calibration of main destination choice.");
        //Todo: obtain the updated coefficients + calibration factors
        Map<Purpose, Map<String, Double>> finalCoefficientsTableMain = destinationChoiceModel.obtainCoefficientsTableMain();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTableMain);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {
        //todo add objective average distance
        objectiveMainDestinationAverageDistance_km.replace(Purpose.WORK, 10.45); //14.5973
        objectiveMainDestinationAverageDistance_km.replace(Purpose.EDUCATION, 6.9366);
        objectiveMainDestinationAverageDistance_km.replace(Purpose.ACCOMPANY, 7.7992);
        objectiveMainDestinationAverageDistance_km.replace(Purpose.SHOPPING, 4.5904);
        objectiveMainDestinationAverageDistance_km.replace(Purpose.OTHER, 8.5788);
        objectiveMainDestinationAverageDistance_km.replace(Purpose.RECREATION, 11.0121);

        objectiveMainDestinationDistBins.get(Purpose.WORK).put(0, 0.1834);
        objectiveMainDestinationDistBins.get(Purpose.EDUCATION).put(0, 0.4235);
        objectiveMainDestinationDistBins.get(Purpose.ACCOMPANY).put(0, 0.3708);
        objectiveMainDestinationDistBins.get(Purpose.SHOPPING).put(0, 0.4998);
        objectiveMainDestinationDistBins.get(Purpose.OTHER).put(0, 0.3889);
        objectiveMainDestinationDistBins.get(Purpose.RECREATION).put(0, 0.3043);

    }

    private void summarizeSimulatedResult() {
        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedMainDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);
            for (int i = 0; i <= 40; i += 2) {
                simulatedMainDestinationDistBins.get(purpose).put(i, 0.0);
            }
        }
        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    for (Tour tour : person.getPlan().getTours().values()) {
                        Purpose mainPurpose = tour.getMainActivity().getPurpose();
                        if (person.getOccupation().equals(Occupation.EMPLOYED) && tour.getMainActivity().getPurpose().equals(Purpose.WORK)) {
                            break;
                        }
                        if (person.getOccupation().equals(Occupation.STUDENT) && tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)) {
                            break;
                        }
                        double distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(household.getLocation(), tour.getMainActivity().getLocation(), Mode.UNKNOWN, 0.);
                        double distanceInKm = distanceInMeters / 1000;
                        int distanceInKmRounded = (int) Math.floor(distanceInKm);
                        if (distanceInKmRounded % 2 == 1) {
                            distanceInKmRounded = (distanceInKmRounded - 1);
                        }
                        if (distanceInKmRounded > 40) {
                            distanceInKmRounded = 40;
                        }
                        //here actually is the total distance for each purpose
                        simulatedMainDestinationAverageDistance_km.put(mainPurpose, simulatedMainDestinationAverageDistance_km.get(mainPurpose) + distanceInKm);
                        simulatedMainDestinationDistBins.get(mainPurpose).put(distanceInKmRounded, simulatedMainDestinationDistBins.get(mainPurpose).get(distanceInKmRounded) + 1);
                        numberOfAct.put(mainPurpose, numberOfAct.get(mainPurpose) + 1);
                    }
                }
            }
        }
        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedMainDestinationAverageDistance_km.put(purpose, simulatedMainDestinationAverageDistance_km.get(purpose) / (double) numberOfAct.get(purpose));
            simulatedMainDestinationDistBins.get(purpose).forEach((distance, count) -> simulatedMainDestinationDistBins.get(purpose).put(distance, count / (double) numberOfAct.get(purpose)));
        }
    }

    private void printFinalCoefficientsTable(Map<Purpose, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing main destination choice coefficient + calibration factors: " + inputFolder);
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

        PrintWriter pw2 = new PrintWriter("input/models/destinationChoice/distDistribution_main_logsum.csv");
        pw2.println("purpose, alpha, beta, distance, share");
        for (Purpose purpose : Purpose.getAllPurposes()) {
            for (int i = 0; i <= 40; i += 2) {
                String line2 = purpose.toString() + "," +
                        finalCoefficientsTable.get(purpose).get("ALPHA") +
                        "," +
                        finalCoefficientsTable.get(purpose).get("BETA") * finalCoefficientsTable.get(purpose).get("BETA_calibration") +
                        "," +
                        i +
                        "," +
                        simulatedMainDestinationDistBins.get(purpose).get(i);
                pw2.println(line2);
            }
        }
        pw2.close();
    }
}
