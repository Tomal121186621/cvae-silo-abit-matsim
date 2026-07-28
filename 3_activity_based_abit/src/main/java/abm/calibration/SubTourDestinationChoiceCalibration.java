package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.activityGeneration.frequency.SubtourGeneratorModel;
import abm.models.destinationChoice.SubtourDestinationChoiceModel;
import abm.properties.AbitResources;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class SubTourDestinationChoiceCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(SubTourDestinationChoiceCalibration.class);
    private static final int MAX_ITERATION = 2_000_000;
    private static final double TERMINATION_THRESHOLD_AVERAGE_DISTANCE = 0.5;
    double stepSize = 0.1;

    String inputFolder = AbitResources.instance.getString("subtour.destination.output");
    DataSet dataSet;

    Map<Purpose, Double> objectiveAverageDistance = new HashMap<>();

    Map<Purpose, Double> simulatedAverageDistance = new HashMap<>();
    Map<Purpose, Integer> simulatedSubtourCount = new HashMap<>();

    Map<Purpose, Double> calibrationFactors = new HashMap<>();
    Map<Purpose, Double> finalCalibrationFactors = new HashMap<>();

    private SubtourDestinationChoiceModel subtourDestinationChoiceModel;

    public SubTourDestinationChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateSubtourDestinationChoiceModel = Boolean.parseBoolean(AbitResources.instance.getString("subtour.destination.calibration"));
        subtourDestinationChoiceModel = new SubtourDestinationChoiceModel(dataSet, calibrateSubtourDestinationChoiceModel);
        //Todo: initialize all the data containers that might be needed for calibration
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            objectiveAverageDistance.put(purpose, 0.0);
            simulatedAverageDistance.put(purpose, 0.0);
            simulatedSubtourCount.put(purpose, 0);
            calibrationFactors.put(purpose, 1.0);
            finalCalibrationFactors.put(purpose, 1.0);
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
        logger.info("Start calibrating the subtour destination choice model......");

        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;
            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                double differenceAverageDistance = 0.0;
                double factor = stepSize * (objectiveAverageDistance.get(purpose) - simulatedAverageDistance.get(purpose));
                differenceAverageDistance = Math.abs(objectiveAverageDistance.get(purpose) - simulatedAverageDistance.get(purpose));

                calibrationFactors.replace(purpose, factor);
                logger.info("Subtour destination choice for" + purpose + "\t" + "average distance: " + simulatedAverageDistance.get(purpose));
                if (differenceAverageDistance > maxDifference) {
                    maxDifference = differenceAverageDistance;
                }

            }
            if (maxDifference <= TERMINATION_THRESHOLD_AVERAGE_DISTANCE) {
                break;
            }

            subtourDestinationChoiceModel.updateCalibration(calibrationFactors);
            subtourDestinationChoiceModel.updateUtilities();

            List<Household> simulatedHouseholds = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());
            simulatedHouseholds.parallelStream().forEach(household -> {
                household.getPersons().stream().forEach(person -> {
                    for (Tour tour : person.getPlan().getTours().values()) {
                        if (tour.getMainActivity().getSubtour() != null) {
                            subtourDestinationChoiceModel.chooseSubtourDestination(tour.getMainActivity().getSubtour().getSubtourActivity(), tour.getMainActivity());
                        }
                    }
                });
            });
            summarizeSimulatedResult();
        }

        logger.info("Finished the calibration of subtour destination choice.");
        //Todo: obtain the updated coefficients + calibration factors
        finalCalibrationFactors = subtourDestinationChoiceModel.obtainCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCalibrationFactors);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {
        objectiveAverageDistance.put(Purpose.WORK, 1.2678);
        objectiveAverageDistance.put(Purpose.EDUCATION, 1.2678);
    }

    private void summarizeSimulatedResult() {
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            simulatedAverageDistance.put(purpose, 0.0);
            simulatedSubtourCount.put(purpose, 0);
        }

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    Plan plan = person.getPlan();
                    for (Tour tour : plan.getTours().values()) {
                        if ((tour.getMainActivity().getPurpose().equals(Purpose.WORK) || tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)) && tour.getMainActivity().getSubtour() != null) {
                            int tourCount = simulatedSubtourCount.get(tour.getMainActivity().getPurpose());
                            simulatedSubtourCount.replace(tour.getMainActivity().getPurpose(), tourCount + 1);
                            double distance = (double) this.dataSet.getTravelDistances().getTravelDistanceInMeters(tour.getMainActivity().getLocation(), tour.getMainActivity().getSubtour().getSubtourActivity().getLocation(), Mode.UNKNOWN, 0.0) / 1000;
                            simulatedAverageDistance.replace(tour.getMainActivity().getPurpose(), simulatedAverageDistance.get(tour.getMainActivity().getPurpose()) + distance);
                        }
                    }
                }
            }
        }

        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            int subtourCount = simulatedSubtourCount.get(purpose);
            double totalDistance = simulatedAverageDistance.get(purpose);
            double averageDistance = (double) totalDistance / subtourCount;
            simulatedAverageDistance.replace(purpose, averageDistance);
        }
    }

    private void printFinalCoefficientsTable(Map<Purpose, Double> finalCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing subtour destination choice coefficient + calibration factors: " + inputFolder);
        PrintWriter pw = new PrintWriter(inputFolder);

        StringBuilder header = new StringBuilder("variable");
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            header.append(",");
            header.append(purpose);
        }
        pw.println(header);

        StringBuilder line = new StringBuilder("calibration");
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            line.append(",");
            line.append(finalCoefficientsTable.get(purpose));
        }
        pw.println(line);

        pw.close();
    }
}
