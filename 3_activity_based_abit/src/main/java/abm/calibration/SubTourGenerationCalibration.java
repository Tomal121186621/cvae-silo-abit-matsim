package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.activityGeneration.frequency.SubtourGeneratorModel;
import abm.models.modeChoice.NestedLogitHabitualModeChoiceModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

public class SubTourGenerationCalibration implements ModelComponent {
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(SubTourGenerationCalibration.class);
    private static final int MAX_ITERATION = 2_000_000;
    private static final double TERMINATION_THRESHOLD = 0.002;
    double stepSize = 0.5;
    String inputFolderWorkSubtour = AbitResources.instance.getString("actgen.subtour.work.output");
    String inputFolderEducationSubtour = AbitResources.instance.getString("actgen.subtour.education.output");
    DataSet dataSet;

    Map<Purpose, Map<Boolean, Double>> objectiveSubtourFrequencyShare = new HashMap<>();

    Map<Purpose, Map<Boolean, Integer>> simulatedSubtourFrequencyCount = new HashMap<>();
    Map<Purpose, Map<Boolean, Integer>> simulatedSubtourFrequencyCountOnTheFly = new HashMap<>();

    Map<Purpose, Integer> simulatedTourCount = new HashMap<>();
    Map<Purpose, Integer> simulatedTourCountOnTheFly = new HashMap<>();

    Map<Purpose, Map<Boolean, Double>> simulatedSubtourFrequencyShare = new HashMap<>();

    Map<Purpose, Map<Boolean, Double>> calibrationFactors = new HashMap<>();
    private SubtourGeneratorModel subtourGeneratorModel;

    public SubTourGenerationCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateSubtourGenerationModel = Boolean.parseBoolean(AbitResources.instance.getString("actgen.subtour.calibration"));
        subtourGeneratorModel = new SubtourGeneratorModel(dataSet, calibrateSubtourGenerationModel);
        //Todo: initialize all the data containers that might be needed for calibration
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            objectiveSubtourFrequencyShare.putIfAbsent(purpose, new HashMap<>());
            objectiveSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.TRUE, 0.0);
            objectiveSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.FALSE, 0.0);

            simulatedSubtourFrequencyCount.putIfAbsent(purpose, new HashMap<>());
            simulatedSubtourFrequencyCount.get(purpose).putIfAbsent(Boolean.TRUE, 0);
            simulatedSubtourFrequencyCount.get(purpose).putIfAbsent(Boolean.FALSE, 0);

            simulatedSubtourFrequencyCountOnTheFly.putIfAbsent(purpose, new HashMap<>());
            simulatedSubtourFrequencyCountOnTheFly.get(purpose).putIfAbsent(Boolean.TRUE, 0);
            simulatedSubtourFrequencyCountOnTheFly.get(purpose).putIfAbsent(Boolean.FALSE, 0);

            simulatedTourCount.putIfAbsent(purpose, 0);

            simulatedTourCountOnTheFly.putIfAbsent(purpose, 0);

            simulatedSubtourFrequencyShare.putIfAbsent(purpose, new HashMap<>());
            simulatedSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.TRUE, 0.0);
            simulatedSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.FALSE, 0.0);

            calibrationFactors.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.get(purpose).putIfAbsent(Boolean.TRUE, 0.0);
            calibrationFactors.get(purpose).putIfAbsent(Boolean.FALSE, 0.0);
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
        logger.info("Start calibrating the subtour generation model......");

        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            logger.info("Iteration......" + iteration);
            double maxDifference = 0.0;

            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                double observedShare = objectiveSubtourFrequencyShare.get(purpose).get(Boolean.TRUE);
                double simulatedShare = simulatedSubtourFrequencyShare.get(purpose).get(Boolean.TRUE);
                double difference = observedShare - simulatedShare;
                logger.info("Subtour generation model for " + purpose.toString() + "\t" + "difference: " + difference);
            }

            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                double observedShare = objectiveSubtourFrequencyShare.get(purpose).get(Boolean.TRUE);
                double simulatedShare = simulatedSubtourFrequencyShare.get(purpose).get(Boolean.TRUE);
                double difference = observedShare - simulatedShare;
                double factor = stepSize * (observedShare - simulatedShare);
                calibrationFactors.get(purpose).replace(Boolean.TRUE, factor);
                logger.info("Subtour generation model for " + purpose.toString() + "\t" + "difference: " + difference);
                if (Math.abs(difference) > maxDifference) {
                    maxDifference = Math.abs(difference);
                }
            }

            subtourGeneratorModel.updateCalibrationFactor(calibrationFactors);

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            } else {
                logger.info("MAX Diff: " + maxDifference);
            }

            //Todo maybe need to reset maps to 0 here


            dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated)
                    .flatMap(household -> household.getPersons().stream())
                    .forEach(person -> {
                        Plan plan = person.getPlan();
                        for (Tour tour : plan.getTours().values()) {
                            if (tour.getMainActivity().getPurpose().equals(Purpose.WORK) || tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)) {
                                boolean hasSubtour = subtourGeneratorModel.hasSubtourInMandatoryActivity(tour);
                                int initialcount = simulatedSubtourFrequencyCountOnTheFly.get(tour.getMainActivity().getPurpose()).get(hasSubtour);
                                simulatedSubtourFrequencyCountOnTheFly.get(tour.getMainActivity().getPurpose()).replace(hasSubtour, initialcount+1);
                            }
                        }
                    });

            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                int newTotalCountPerPurpose = simulatedSubtourFrequencyCountOnTheFly.get(purpose).get(Boolean.TRUE) + simulatedSubtourFrequencyCountOnTheFly.get(purpose).get(Boolean.FALSE);
                simulatedTourCountOnTheFly.replace(purpose, newTotalCountPerPurpose);
                int trueCount = simulatedSubtourFrequencyCountOnTheFly.get(purpose).get(Boolean.TRUE);
                double trueShare = (double) trueCount / newTotalCountPerPurpose;
                simulatedSubtourFrequencyShare.get(purpose).replace(Boolean.TRUE, trueShare);
                simulatedSubtourFrequencyShare.get(purpose).replace(Boolean.FALSE, 1 - trueShare);

            }

            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                simulatedSubtourFrequencyCountOnTheFly.get(purpose).putIfAbsent(Boolean.TRUE, 0);
                simulatedSubtourFrequencyCountOnTheFly.get(purpose).putIfAbsent(Boolean.FALSE, 0);
                simulatedTourCountOnTheFly.putIfAbsent(purpose, 0);
                simulatedSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.TRUE, 0.0);
                simulatedSubtourFrequencyShare.get(purpose).putIfAbsent(Boolean.FALSE, 0.0);
            }

        }

        logger.info("Finished the calibration of subtour generation model.");

        //Todo: obtain the updated coefficients + calibration factors
        Map<Purpose, Map<String, Double>> finalCoefficientsTable = subtourGeneratorModel.obtainCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTable);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {
        objectiveSubtourFrequencyShare.get(Purpose.WORK).put(Boolean.TRUE, 0.0616);
        objectiveSubtourFrequencyShare.get(Purpose.WORK).put(Boolean.FALSE, 0.9384);
        objectiveSubtourFrequencyShare.get(Purpose.EDUCATION).put(Boolean.TRUE, 0.0335);
        objectiveSubtourFrequencyShare.get(Purpose.EDUCATION).put(Boolean.FALSE, 0.9665);
    }

    private void summarizeSimulatedResult() {

        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            simulatedTourCount.put(purpose, 0);
            simulatedSubtourFrequencyCount.get(purpose).put(Boolean.TRUE, 0);
            simulatedSubtourFrequencyCount.get(purpose).put(Boolean.FALSE, 0);
            simulatedSubtourFrequencyShare.get(purpose).put(Boolean.TRUE, 0.0);
            simulatedSubtourFrequencyShare.get(purpose).put(Boolean.FALSE, 0.0);
        }

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    Plan plan = person.getPlan();
                    for (Tour tour : plan.getTours().values()) {
                        if (tour.getMainActivity().getPurpose().equals(Purpose.WORK)) {
                            int tourCount = simulatedTourCount.get(tour.getMainActivity().getPurpose());
                            simulatedTourCount.replace(tour.getMainActivity().getPurpose(), tourCount + 1);
                            if (tour.getMainActivity().getSubtour() != null) {
                                int trueCount = simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).get(Boolean.TRUE);
                                simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).replace(Boolean.TRUE, trueCount + 1);
                            } else {
                                int falseCount = simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).get(Boolean.FALSE);
                                simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).replace(Boolean.FALSE, falseCount + 1);
                            }
                        } else if (tour.getMainActivity().getPurpose().equals(Purpose.EDUCATION)) {
                            int tourCount = simulatedTourCount.get(tour.getMainActivity().getPurpose());
                            simulatedTourCount.replace(tour.getMainActivity().getPurpose(), tourCount + 1);
                            if (tour.getMainActivity().getSubtour() != null) {
                                int trueCount = simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).get(Boolean.TRUE);
                                simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).replace(Boolean.TRUE, trueCount + 1);
                            } else {
                                int falseCount = simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).get(Boolean.FALSE);
                                simulatedSubtourFrequencyCount.get(tour.getMainActivity().getPurpose()).replace(Boolean.FALSE, falseCount + 1);
                            }
                        } else {
                        }
                    }
                }
            }
        }

        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            int popCount = simulatedTourCount.get(purpose);
            int trueCount = simulatedSubtourFrequencyCount.get(purpose).get(Boolean.TRUE);
            double trueShare = (double) trueCount / popCount;
            simulatedSubtourFrequencyShare.get(purpose).replace(Boolean.TRUE, trueShare);
            simulatedSubtourFrequencyShare.get(purpose).replace(Boolean.FALSE, 1 - trueShare);
        }

    }

    private void printFinalCoefficientsTable(Map<Purpose, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {

        logger.info("Writing subtour generation coefficient + calibration factors for work: " + inputFolderWorkSubtour);

        PrintWriter pwWorkSubtour = new PrintWriter(inputFolderWorkSubtour);

        StringBuilder headerWork = new StringBuilder("variable");
        headerWork.append(",");
        headerWork.append("no");
        headerWork.append(",");
        headerWork.append("yes");

        pwWorkSubtour.println(headerWork);

        for (String variableNames : finalCoefficientsTable.get(Purpose.WORK).keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            line.append(",");
            line.append(0);
            line.append(",");
            line.append(finalCoefficientsTable.get(Purpose.WORK).get(variableNames));
            pwWorkSubtour.println(line);
        }
        pwWorkSubtour.close();

        logger.info("Writing subtour generation coefficient + calibration factors for education: " + inputFolderEducationSubtour);

        PrintWriter pwEduSubtour = new PrintWriter(inputFolderEducationSubtour);

        StringBuilder headerEducation = new StringBuilder("variable");
        headerEducation.append(",");
        headerEducation.append("no");
        headerEducation.append(",");
        headerEducation.append("yes");

        pwEduSubtour.println(headerEducation);

        for (String variableNames : finalCoefficientsTable.get(Purpose.EDUCATION).keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            line.append(",");
            line.append(0);
            line.append(",");
            line.append(finalCoefficientsTable.get(Purpose.EDUCATION).get(variableNames));
            pwEduSubtour.println(line);
        }
        pwEduSubtour.close();

    }
}
