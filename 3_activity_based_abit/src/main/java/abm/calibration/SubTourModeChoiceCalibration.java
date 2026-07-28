package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.modeChoice.SubtourModeChoiceModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class SubTourModeChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(SubTourModeChoiceCalibration.class);
    private static final int MAX_ITERATION = 2_000_000;
    private static final double TERMINATION_THRESHOLD = 0.005;
    double stepSize = 0.1;
    String inputFolder = AbitResources.instance.getString("mode.choice.subtour.output");
    DataSet dataSet;

    Map<String, Double> objectiveSubtourModeShare = new HashMap<>();

    Map<String, Integer> simulatedSubtourModeCount = new HashMap<>();

    Map<String, Double> simulatedSubtourModeShare = new HashMap<>();

    Map<String, Double> calibrationFactors = new HashMap<>();

    Map<String, Double> finalCoefficients = new HashMap<>();
    private SubtourModeChoiceModel subtourModeChoiceModel;

    public SubTourModeChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateSubtourModeChoiceModel = Boolean.parseBoolean(AbitResources.instance.getString("mode.choice.subtour.calibration"));
        subtourModeChoiceModel = new SubtourModeChoiceModel(dataSet, calibrateSubtourModeChoiceModel);

        //Todo: initialize all the data containers that might be needed for calibration
        objectiveSubtourModeShare.putIfAbsent("sameAsMainMode", 0.0);
        objectiveSubtourModeShare.putIfAbsent("switchToWalk", 0.0);

        simulatedSubtourModeCount.putIfAbsent("sameAsMainMode", 0);
        simulatedSubtourModeCount.putIfAbsent("switchToWalk", 0);

        simulatedSubtourModeShare.putIfAbsent("sameAsMainMode", 0.0);
        simulatedSubtourModeShare.putIfAbsent("switchToWalk", 0.0);

        calibrationFactors.putIfAbsent("sameAsMainMode", 0.0);
        calibrationFactors.putIfAbsent("switchToWalk", 0.0);
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
        logger.info("Start calibrating the subtour mode choice model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            logger.info("Iteration......" + iteration);
            double maxDifference = 0.0;

            double observedWalkShare = objectiveSubtourModeShare.get("switchToWalk");
            double simulatedWalkShare = simulatedSubtourModeShare.get("switchToWalk");
            double differenceWalkShare = observedWalkShare - simulatedWalkShare;
            logger.info("Subtour mode choice model for walk" + "\t" + "difference: " + differenceWalkShare);

            double factor = stepSize * differenceWalkShare;
            calibrationFactors.replace("switchToWalk", factor);

            if (Math.abs(differenceWalkShare) > maxDifference) {
                maxDifference = Math.abs(differenceWalkShare);
            }

            subtourModeChoiceModel.updateCalibrationFactor(calibrationFactors);

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            } else {
                logger.info("MAX Diff: " + maxDifference);
            }

            List<Household> simulatedHouseholds = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());
            simulatedHouseholds.parallelStream().forEach(household -> {
                household.getPersons().stream().forEach(person -> {
                    for (Tour tour : person.getPlan().getTours().values()) {
                        if (tour.getMainActivity().getSubtour() != null) {
                            subtourModeChoiceModel.chooseSubtourMode(tour);
                        }
                    }
                });
            });
            summarizeSimulatedResult();
        }
        logger.info("Finished the calibration of subtour mode choice choice.");
        //Todo: obtain the updated coefficients + calibration factors
        finalCoefficients = subtourModeChoiceModel.obtainCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficients);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {
        objectiveSubtourModeShare.replace("sameAsMainMode", 0.4837);
        objectiveSubtourModeShare.replace("switchToWalk", 0.5163);
    }

    private void summarizeSimulatedResult() {

        int tourCount = 0;

        simulatedSubtourModeCount.put("sameAsMainMode", 0);
        simulatedSubtourModeCount.put("switchToWalk", 0);
        simulatedSubtourModeShare.put("sameAsMainMode", 0.0);
        simulatedSubtourModeShare.put("switchToWalk", 0.0);

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    Plan plan = person.getPlan();
                    for (Tour tour : plan.getTours().values()) {
                        if ((tour.getMainActivity().getPurpose().equals(Purpose.WORK) || tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)) && tour.getMainActivity().getSubtour() != null) {
                            tourCount += 1;
                            if (tour.getMainActivity().getSubtour().getInboundLeg().getLegMode().equals(Mode.WALK)) {
                                int walkCount = simulatedSubtourModeCount.get("switchToWalk");
                                simulatedSubtourModeCount.replace("switchToWalk", walkCount + 1);
                            } else {
                                int otherModeCount = simulatedSubtourModeCount.get("sameAsMainMode");
                                simulatedSubtourModeCount.replace("sameAsMainMode", otherModeCount + 1);
                            }
                        }
                    }
                }
            }
        }

        int switchToWalkCount = simulatedSubtourModeCount.get("switchToWalk");
        double switchToWalkCountShare = (double) switchToWalkCount / tourCount;
        simulatedSubtourModeShare.replace("switchToWalk", switchToWalkCountShare);
        simulatedSubtourModeShare.replace("sameAsMainMode", 1 - switchToWalkCountShare);

    }

    private void printFinalCoefficientsTable(Map<String, Double> finalCoefficientsTable) throws FileNotFoundException {

        logger.info("Writing subtour mode choice coefficient + calibration factors for work: " + inputFolder);

        PrintWriter pw = new PrintWriter(inputFolder);

        StringBuilder headerWork = new StringBuilder("variable");
        headerWork.append(",");
        headerWork.append("sameAsMainMode");
        headerWork.append(",");
        headerWork.append("switchToWalk");

        pw.println(headerWork);

        for (String variableNames : finalCoefficientsTable.keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            line.append(",");
            line.append(0);
            line.append(",");
            line.append(finalCoefficientsTable.get(variableNames));
            pw.println(line);
        }

        pw.close();


    }
}
