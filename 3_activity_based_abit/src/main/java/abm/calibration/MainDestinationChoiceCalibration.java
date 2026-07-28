package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.destinationChoice.DestinationChoiceModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class MainDestinationChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(MainDestinationChoiceCalibration.class);
    private static final int MAX_ITERATION = 100;//2_000_000;
    private static final double TERMINATION_THRESHOLD = 1.0;
    double stepSize = 0.0005;

    private final int NUMBER_OF_BINS = 10;
    String inputFolder = AbitResources.instance.getString("destination.choice.main.act.output");
    DataSet dataSet;
    Map<Purpose, Map<Integer, Double>> objectiveMainDestinationDistanceShare = new HashMap<>();
    Map<Purpose, Double> objectiveMainDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Map<Integer, Integer>> simulatedMainDestinationDistanceCount = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> simulatedMainDestinationDistanceShare = new HashMap<>();

    Map<Purpose, Double> simulatedMainDestinationAverageDistance_km = new HashMap<>();
    Map<Purpose, Integer> numberOfAct = new HashMap<>();
    Map<Purpose, Map<String, Double>> calibrationFactors = new HashMap<>();
    private DestinationChoiceModel destinationChoiceModel;


    public MainDestinationChoiceCalibration(DataSet dataSet) {
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
            objectiveMainDestinationDistanceShare.putIfAbsent(purpose, new HashMap<>());
            simulatedMainDestinationDistanceCount.putIfAbsent(purpose, new HashMap<>());
            simulatedMainDestinationDistanceShare.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.get(purpose).put("ALPHA_calibration", 0.);
            calibrationFactors.get(purpose).put("BETA_calibration", 0.);
            simulatedMainDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);

            for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                objectiveMainDestinationDistanceShare.get(purpose).put(i, 0.);
                simulatedMainDestinationDistanceCount.get(purpose).put(i, 0);
                simulatedMainDestinationDistanceShare.get(purpose).put(i, 0.);

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
        logger.info("Start calibrating the main destination choice model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;
            for (Purpose purpose : Purpose.getAllPurposes()) {
//                double[] observedTotalBinShare = new double[NUMBER_OF_BINS];
//                double[] simulatedTotalBinShare = new double[NUMBER_OF_BINS];
//                double differenceTotalBinShare = 0.0;
//                for (int i = 1; i <= NUMBER_OF_BINS; i++) {
//                    observedTotalBinShare[i-1] = objectiveMainDestinationDistanceShare.get(purpose).get(i);
//                    simulatedTotalBinShare[i-1] = simulatedMainDestinationDistanceShare.get(purpose).get(i);
//                    double differenceForBin = observedTotalBinShare[i-1] - simulatedTotalBinShare[i-1];
//                    differenceTotalBinShare += Math.abs(differenceForBin);
//                }

                double differenceAverageDistance = 0.0;
                double factor = (simulatedMainDestinationAverageDistance_km.get(purpose) / objectiveMainDestinationAverageDistance_km.get(purpose));
                factor = Math.max(factor, 0.5);
                factor = Math.min(factor, 2);
                differenceAverageDistance = Math.abs(objectiveMainDestinationAverageDistance_km.get(purpose) - simulatedMainDestinationAverageDistance_km.get(purpose));


                //todo calculate the difference between observed and simulated average distance
                //if observation > simulation, beta should be increased (-1.0 ->-0.5)
                //if observation < simulation, beta should be decreased (-1.0 -> -1.5)
                //double factor = stepSize * (objectiveMainDestinationAverageDistance_km.get(purpose) - simulatedMainDestinationAverageDistance_km.get(purpose));
//                if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION)) {
//                    factor = 0;
//                    differenceTotalBinShare = 0;
//                }

                if (purpose.equals(Purpose.EDUCATION)){
                    calibrationFactors.get(purpose).replace("BETA_calibration", 1.0);
                }else{
                    calibrationFactors.get(purpose).replace("BETA_calibration", factor);
                }

                //logger.info("Main destination choice for" + purpose.toString() + "\t" + "difference: " + differenceTotalBinShare);
                logger.info("Main destination choice for" + purpose + "\t" + "average distance: " + simulatedMainDestinationAverageDistance_km.get(purpose));
                if (!purpose.equals(Purpose.WORK) && !purpose.equals(Purpose.EDUCATION)) {
                    if (Math.abs(differenceAverageDistance) > maxDifference) {
                        maxDifference = differenceAverageDistance;
                    }
                }

            }
            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            }

            destinationChoiceModel.updateCalibrationFactorsMain(calibrationFactors);
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
        // each bin is 2km wide, from 0 to 20 km, 10 bins in total.
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(1, 0.1649);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(2, 0.1692);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(3, 0.1334);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(4, 0.1196);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(5, 0.0819);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(6, 0.0645);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(7, 0.0575);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(8, 0.0366);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(9, 0.0307);
        objectiveMainDestinationDistanceShare.get(Purpose.WORK).put(10, 0.0256);

        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(1, 0.5319);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(2, 0.2327);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(3, 0.0862);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(4, 0.0427);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(5, 0.0237);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(6, 0.0136);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(7, 0.0129);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(8, 0.0068);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(9, 0.0041);
        objectiveMainDestinationDistanceShare.get(Purpose.EDUCATION).put(10, 0.0014);

        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(1, 0.5047);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(2, 0.1964);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(3, 0.0989);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(4, 0.0530);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(5, 0.0315);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(6, 0.0186);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(7, 0.0129);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(8, 0.0100);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(9, 0.0036);
        objectiveMainDestinationDistanceShare.get(Purpose.ACCOMPANY).put(10, 0.0050);

        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(1, 0.4166);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(2, 0.2542);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(3, 0.1113);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(4, 0.0612);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(5, 0.0389);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(6, 0.0261);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(7, 0.0159);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(8, 0.0153);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(9, 0.0051);
        objectiveMainDestinationDistanceShare.get(Purpose.SHOPPING).put(10, 0.0057);

        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(1, 0.3664);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(2, 0.1880);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(3, 0.1094);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(4, 0.0950);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(5, 0.0560);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(6, 0.0273);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(7, 0.0226);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(8, 0.0185);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(9, 0.0116);
        objectiveMainDestinationDistanceShare.get(Purpose.OTHER).put(10, 0.0137);

        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(1, 0.3704);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(2, 0.2040);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(3, 0.1107);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(4, 0.0742);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(5, 0.0467);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(6, 0.0309);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(7, 0.0354);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(8, 0.0275);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(9, 0.0124);
        objectiveMainDestinationDistanceShare.get(Purpose.RECREATION).put(10, 0.0118);

        //todo add objective average distance
        objectiveMainDestinationAverageDistance_km.put(Purpose.WORK, 17.0369);
        objectiveMainDestinationAverageDistance_km.put(Purpose.EDUCATION, 11.1591);
        objectiveMainDestinationAverageDistance_km.put(Purpose.ACCOMPANY, 7.9266);
        objectiveMainDestinationAverageDistance_km.put(Purpose.SHOPPING, 5.4520);
        objectiveMainDestinationAverageDistance_km.put(Purpose.OTHER, 9.4005);
        objectiveMainDestinationAverageDistance_km.put(Purpose.RECREATION, 10.5703);

    }

    private void summarizeSimulatedResult() {

        for (Purpose purpose : Purpose.getAllPurposes()) {
            simulatedMainDestinationAverageDistance_km.put(purpose, 0.);
            numberOfAct.put(purpose, 0);
            for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                simulatedMainDestinationDistanceCount.get(purpose).put(i, 0);
                simulatedMainDestinationDistanceShare.get(purpose).put(i, 0.);
            }
        }



        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    for (Tour tour : person.getPlan().getTours().values()){
                        Purpose mainPurpose = tour.getMainActivity().getPurpose();

                        if (person.getOccupation().equals(Occupation.EMPLOYED) && tour.getMainActivity().getPurpose().equals(Purpose.WORK)){
                            break;
                        }
                        if (person.getOccupation().equals(Occupation.STUDENT) && tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)){
                            break;
                        }

                        double distanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(household.getLocation(), tour.getMainActivity().getLocation(), Mode.UNKNOWN, 0.);
                        double distanceInKm = distanceInMeters / 1000;
                        int indexOfBin = 0;
                        if ((int) Math.floor(distanceInKm) % 2 == 0) {
                            indexOfBin = (int) Math.floor(distanceInKm) / 2 + 1;
                        } else {
                            indexOfBin = ((int) Math.floor(distanceInKm) + 1) / 2;
                        }
                        if (indexOfBin <= NUMBER_OF_BINS) {
                            simulatedMainDestinationDistanceCount.get(mainPurpose).put(indexOfBin, simulatedMainDestinationDistanceCount.get(mainPurpose).get(indexOfBin) + 1);
                        }


                        //here actually is the total distance for each purpose
                        simulatedMainDestinationAverageDistance_km.put(mainPurpose, simulatedMainDestinationAverageDistance_km.get(mainPurpose) + distanceInKm);
                        numberOfAct.put(mainPurpose, numberOfAct.get(mainPurpose) + 1);
                    }

                }
            }
        }
        for (Purpose purpose : Purpose.getAllPurposes()) {
            for (int i = 1; i <= NUMBER_OF_BINS; i++) {
                simulatedMainDestinationDistanceShare.get(purpose).put(i,  (double) simulatedMainDestinationDistanceCount.get(purpose).get(i) / (double) numberOfAct.get(purpose));
            }
            simulatedMainDestinationAverageDistance_km.put(purpose, simulatedMainDestinationAverageDistance_km.get(purpose) / (double)numberOfAct.get(purpose));
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
            for (Purpose purpose : Purpose.getAllPurposes()){
                line.append(",");
                line.append(finalCoefficientsTable.get(purpose).get(variableNames));

            }
            pw.println(line);
        }
        pw.close();

    }
}
