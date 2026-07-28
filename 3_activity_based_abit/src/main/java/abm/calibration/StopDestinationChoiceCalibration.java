package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.destinationChoice.DestinationChoiceModel;
import abm.properties.AbitResources;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class StopDestinationChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(StopDestinationChoiceCalibration.class);
    private static final int MAX_ITERATION = 100; //2_000_000;
    private static final double TERMINATION_THRESHOLD_AVERAGE_DISTANCE = 1.00;
    double stepSize = 0.01;

    private final int NUMBER_OF_BINS = 10;
    String inputFolder = AbitResources.instance.getString("destination.choice.stop.act.output");
    DataSet dataSet;
    Map<Purpose, Map<Integer, Double>> objectiveStopDestinationDistanceShare = new HashMap<>();
    Map<Purpose, Double> objectiveStopDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Map<Integer, Integer>> simulatedStopDestinationDistanceCount = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> simulatedStopDestinationDistanceShare = new HashMap<>();
    Map<Purpose, Double> simulatedStopDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Integer> numberOfAct = new HashMap<>();
    Map<Purpose, Map<String, Double>> calibrationFactors = new HashMap<>();

    private DestinationChoiceModel destinationChoiceModel;

    public StopDestinationChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateMainDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.main.destination.calibration"));
        boolean calibrateStopDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.stop.destination.calibration"));
        destinationChoiceModel = new DestinationChoiceModel(dataSet, calibrateMainDestinationChoice, calibrateStopDestinationChoice);
        //Todo: initialize all the data containers that might be needed for calibration
        for (Purpose purpose : Purpose.getAllPurposes()) {
            objectiveStopDestinationDistanceShare.putIfAbsent(purpose, new HashMap<>());
            simulatedStopDestinationDistanceCount.putIfAbsent(purpose, new HashMap<>());
            simulatedStopDestinationDistanceShare.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.get(purpose).put("ALPHA_calibration", 0.);
            calibrationFactors.get(purpose).put("BETA_calibration", 1.);
            simulatedStopDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);
            for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                objectiveStopDestinationDistanceShare.get(purpose).put(i, 0.);
                simulatedStopDestinationDistanceCount.get(purpose).put(i, 0);
                simulatedStopDestinationDistanceShare.get(purpose).put(i, 0.);
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
        logger.info("Start calibrating the stop destination choice model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;
            for (Purpose purpose : Purpose.getAllPurposes()) {
                double[] observedTotalBinShare = new double[NUMBER_OF_BINS];
                double[] simulatedTotalBinShare = new double[NUMBER_OF_BINS];
                double differenceTotalBinShare = 0.0;
                double differenceAverageDistance = 0.0;
//                if (purpose.equals(Purpose.WORK)) {
//                    for (int i = 1; i <= NUMBER_OF_BINS; i++) {
//                        observedTotalBinShare[i-1] = objectiveStopDestinationDistanceShare.get(purpose).get(i);
//                        simulatedTotalBinShare[i-1] = simulatedStopDestinationDistanceShare.get(purpose).get(i);
//                        double differenceForBin = observedTotalBinShare[i-1] - simulatedTotalBinShare[i-1];
//                        differenceTotalBinShare += Math.abs(differenceForBin);
//                    }
//                } else{
//                    for (int i = 1; i <= NUMBER_OF_BINS; i++) {
//                        observedTotalBinShare[i-1] = objectiveStopDestinationDistanceShare.get(purpose).get(i); //+ objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).get(i) + objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).get(i) + objectiveStopDestinationDistanceShare.get(Purpose.OTHER).get(i) + objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).get(i);
//                        simulatedTotalBinShare[i-1] = simulatedStopDestinationDistanceShare.get(purpose).get(i); //+ simulatedStopDestinationDistanceShare.get(Purpose.ACCOMPANY).get(i) + simulatedStopDestinationDistanceShare.get(Purpose.SHOPPING).get(i) + simulatedStopDestinationDistanceShare.get(Purpose.OTHER).get(i) + simulatedStopDestinationDistanceShare.get(Purpose.RECREATION).get(i);
//                        double differenceForBin = observedTotalBinShare[i-1] - simulatedTotalBinShare[i-1];
//                        differenceTotalBinShare += Math.abs(differenceForBin);
//                    }
//                }
                double factor = (simulatedStopDestinationAverageDistance_km.get(purpose) / objectiveStopDestinationAverageDistance_km.get(purpose));
                factor = Math.max(factor, 0.5);
                factor = Math.min(factor, 2);
                differenceAverageDistance = Math.abs(objectiveStopDestinationAverageDistance_km.get(purpose) - simulatedStopDestinationAverageDistance_km.get(purpose));

                calibrationFactors.get(purpose).replace("BETA_calibration", factor);
                logger.info("Stop destination choice for" + purpose + "\t" + "average distance: " + simulatedStopDestinationAverageDistance_km.get(purpose));
                if (differenceAverageDistance > maxDifference) {
                    maxDifference = differenceAverageDistance;
                }

            }
            if (maxDifference <= TERMINATION_THRESHOLD_AVERAGE_DISTANCE) {
                break;
            }

            destinationChoiceModel.updateCalibrationFactorsStop(calibrationFactors);
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
        // each bin is 0.2km wide, from 0 to 2 km, 10 bins in total.
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(1, 0.2847);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(2, 0.1746);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(3, 0.1220);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(4, 0.1124);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(5, 0.0478);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(6, 0.1005);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(7, 0.0431);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(8, 0.0167);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(9, 0.0239);
        objectiveStopDestinationDistanceShare.get(Purpose.WORK).put(10, 0.0144);

        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(1, 0.0691);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(2, 0.1223);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(3, 0.1011);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(4, 0.1330);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(5, 0.0851);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(6, 0.1064);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(7, 0.0532);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(8, 0.0372);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(9, 0.0053);
        objectiveStopDestinationDistanceShare.get(Purpose.EDUCATION).put(10, 0.0319);

        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(1, 0.1996);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(2, 0.0599);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(3, 0.0739);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(4, 0.1158);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(5, 0.1078);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(6, 0.0739);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(7, 0.0459);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(8, 0.0359);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(9, 0.0200);
        objectiveStopDestinationDistanceShare.get(Purpose.ACCOMPANY).put(10, 0.0160);

        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(1, 0.3315);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(2, 0.1328);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(3, 0.0831);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(4, 0.0813);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(5, 0.0714);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(6, 0.0687);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(7, 0.0461);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(8, 0.0343);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(9, 0.0163);
        objectiveStopDestinationDistanceShare.get(Purpose.SHOPPING).put(10, 0.0108);

        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(1, 0.2571);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(2, 0.0939);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(3, 0.0898);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(4, 0.0816);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(5, 0.0694);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(6, 0.0612);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(7, 0.0449);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(8, 0.0204);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(9, 0.0367);
        objectiveStopDestinationDistanceShare.get(Purpose.OTHER).put(10, 0.0204);

        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(1, 0.4435);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(2, 0.1532);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(3, 0.0081);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(4, 0.0968);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(5, 0.0323);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(6, 0.0968);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(7, 0.0403);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(8, 0.0);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(9, 0.0);
        objectiveStopDestinationDistanceShare.get(Purpose.RECREATION).put(10, 0.0484);

        //todo add objective average distance
        objectiveStopDestinationAverageDistance_km.put(Purpose.WORK, 4.0565034873952674);
        objectiveStopDestinationAverageDistance_km.put(Purpose.EDUCATION, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.ACCOMPANY, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.SHOPPING, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.OTHER, 3.6220093126038324);
        objectiveStopDestinationAverageDistance_km.put(Purpose.RECREATION, 3.6220093126038324);

    }

    private void summarizeSimulatedResult() {

        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedStopDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);
            for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                simulatedStopDestinationDistanceCount.get(purpose).put(i, 0);
                simulatedStopDestinationDistanceShare.get(purpose).put(i, 0.);
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
                                if (tourPurpose.equals(Purpose.WORK) ) {
                                    distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(household.getLocation(), activity.getLocation(), Mode.UNKNOWN, 0.);
                                } else {
                                    distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(tour.getMainActivity().getLocation(), activity.getLocation(), Mode.UNKNOWN, 0.);
                                }
                                double distanceInKm = distanceInMeters / 1000;
                                int indexOfBin = 0;
                                if ((int) Math.floor(distanceInKm * 10) % 2 == 0) {
                                    indexOfBin = (int) Math.floor(distanceInKm * 10) / 2 + 1;
                                } else {
                                    indexOfBin = ((int) Math.floor(distanceInKm * 10) + 1) / 2;
                                }
                                if (indexOfBin <= NUMBER_OF_BINS) {
                                    simulatedStopDestinationDistanceCount.get(tourPurpose).put(indexOfBin, simulatedStopDestinationDistanceCount.get(tourPurpose).get(indexOfBin) + 1);
                                }
                                //here actually is the total distance for each purpose
                                simulatedStopDestinationAverageDistance_km.put(tourPurpose, simulatedStopDestinationAverageDistance_km.get(tourPurpose) + distanceInKm);
                                numberOfAct.put(tourPurpose, numberOfAct.get(tourPurpose) + 1);
                                break;
                            }
                        }
                    }
                }
            }
        }
        for (Purpose purpose : Purpose.getAllPurposes()) {
            if (purpose.equals(Purpose.WORK)) {
                for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                    simulatedStopDestinationDistanceShare.get(purpose).put(i,  (double)simulatedStopDestinationDistanceCount.get(purpose).get(i) / (double) numberOfAct.get(purpose));
                }
                simulatedStopDestinationAverageDistance_km.put(purpose, simulatedStopDestinationAverageDistance_km.get(purpose) / numberOfAct.get(purpose));

            }else {
                for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                    simulatedStopDestinationDistanceShare.get(purpose).put(i, ((double) (simulatedStopDestinationDistanceCount.get(Purpose.EDUCATION).get(i) + simulatedStopDestinationDistanceCount.get(Purpose.ACCOMPANY).get(i) + simulatedStopDestinationDistanceCount.get(Purpose.SHOPPING).get(i) + simulatedStopDestinationDistanceCount.get(Purpose.OTHER).get(i) + simulatedStopDestinationDistanceCount.get(Purpose.RECREATION).get(i))) / ((double) (numberOfAct.get(Purpose.EDUCATION)+numberOfAct.get(Purpose.ACCOMPANY)+numberOfAct.get(Purpose.SHOPPING)+numberOfAct.get(Purpose.OTHER)+numberOfAct.get(Purpose.RECREATION))));
                }
                simulatedStopDestinationAverageDistance_km.put(purpose, simulatedStopDestinationAverageDistance_km.get(purpose) / numberOfAct.get(purpose));
            }
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

    }
}

