package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.HabitualMode;
import abm.data.plans.Mode;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.modeChoice.NestedLogitHabitualModeChoiceModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;


import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class HabitualModeChoiceCalibration implements ModelComponent {

    static Logger logger = Logger.getLogger(HabitualModeChoiceCalibration.class);
    private static final int MAX_ITERATION = 2_000_000;
    private static final double TERMINATION_THRESHOLD = 0.02;
    double stepSize = 0.5;
    String inputFolder = AbitResources.instance.getString("habitual.mode.calibration.output");
    DataSet dataSet;
    Map<Occupation, Map<HabitualMode, Double>> objectiveHabitualModeShare = new HashMap<>();
    Map<HabitualMode, Double> objectiveHabitualAggreModeShare = new HashMap<>();
    Map<Occupation, Map<HabitualMode, Integer>> simulatedHabitualModeCount = new HashMap<>();
    Map<HabitualMode, Integer> simulatedHabitualAggreModeCount = new HashMap<>();
    Map<Occupation, Integer> simulatedPopCount = new HashMap<>();
    Map<Occupation, Map<HabitualMode, Double>> simulatedHabitualModeShare = new HashMap<>();
    Map<HabitualMode, Double> simulatedHabitualAggreModeShare = new HashMap<>();
    Map<Occupation, Map<HabitualMode, Double>> calibrationFactors = new HashMap<>();
    private NestedLogitHabitualModeChoiceModel habitualModeChoiceCalibration;

    public HabitualModeChoiceCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateHabitualModeChoice = Boolean.parseBoolean(AbitResources.instance.getString("habitual.mode.calibration"));
        habitualModeChoiceCalibration = new NestedLogitHabitualModeChoiceModel(dataSet, calibrateHabitualModeChoice);

        //Todo: initialize all the data containers that might be needed for calibration
        for (Occupation occupation : Occupation.values()) {
            objectiveHabitualModeShare.putIfAbsent(occupation, new HashMap<>());
            simulatedHabitualModeCount.putIfAbsent(occupation, new HashMap<>());
            simulatedPopCount.putIfAbsent(occupation, 0);
            simulatedHabitualModeShare.putIfAbsent(occupation, new HashMap<>());
            calibrationFactors.putIfAbsent(occupation, new HashMap<>());

            for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
                objectiveHabitualModeShare.get(occupation).putIfAbsent(habitualMode, 0.0);
                simulatedHabitualModeCount.get(occupation).putIfAbsent(habitualMode, 0);
                simulatedHabitualModeShare.get(occupation).putIfAbsent(habitualMode, 0.0);
                calibrationFactors.get(occupation).putIfAbsent(habitualMode, 0.0);
                objectiveHabitualAggreModeShare.putIfAbsent(habitualMode, 0.0);
                simulatedHabitualAggreModeCount.putIfAbsent(habitualMode, 0);
                simulatedHabitualAggreModeShare.putIfAbsent(habitualMode, 0.0);
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

        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            logger.info("Iteration......" + iteration);
            double maxDifference = 0.0;

            for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
                double observedAggreShare = objectiveHabitualAggreModeShare.get(habitualMode);
                double simulatedAggreShare = simulatedHabitualAggreModeShare.get(habitualMode);
                double differenceAggre = observedAggreShare - simulatedAggreShare;
                logger.info("Habitual mode choice model for " + habitualMode.toString() + "\t" + "difference: " + differenceAggre);
            }

            for (Occupation occupation : Occupation.values()) {
                for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
                    double observedShare = objectiveHabitualModeShare.get(occupation).get(habitualMode);
                    double simulatedShare = simulatedHabitualModeShare.get(occupation).get(habitualMode);
                    double difference = observedShare - simulatedShare;
                    double factor = stepSize * (observedShare - simulatedShare);
                    if (habitualMode.equals(HabitualMode.CAR_DRIVER)) {
                        factor = 0.00;
                    }
                    calibrationFactors.get(occupation).replace(habitualMode, factor);
                    logger.info("Habitual mode choice model for " + occupation.toString() + "\t" + " and " + habitualMode.toString() + "\t" + "difference: " + difference);
                    if (Math.abs(difference) > maxDifference) {
                        maxDifference = Math.abs(difference);
                    }
                }
            }

            habitualModeChoiceCalibration.updateCalibrationFactor(calibrationFactors);

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            }else {
                logger.info("MAX Diff: " + maxDifference);
            }

            //List<Household> simulatedHousehold = dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated).collect(Collectors.toList());
            //simulatedHousehold.forEach(household -> household.getPersons());

            dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated)
                    .flatMap(household -> household.getPersons().stream())
                    .forEach(p -> habitualModeChoiceCalibration.chooseHabitualMode(p));

            summarizeSimulatedResult();

        }

        logger.info("Finished the calibration of habitual mode choice model.");

        //Todo: obtain the updated coefficients + calibration factors
        Map<HabitualMode, Map<String, Double>> finalCoefficientsTable = habitualModeChoiceCalibration.obtainCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTable);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {

        objectiveHabitualAggreModeShare.put(HabitualMode.CAR_DRIVER, 0.5424);
        objectiveHabitualAggreModeShare.put(HabitualMode.CAR_PASSENGER, 0.0341);
        objectiveHabitualAggreModeShare.put(HabitualMode.PT, 0.2471);
        objectiveHabitualAggreModeShare.put(HabitualMode.BIKE, 0.1270);
        objectiveHabitualAggreModeShare.put(HabitualMode.WALK, 0.0494);

        objectiveHabitualModeShare.get(Occupation.EMPLOYED).put(HabitualMode.CAR_DRIVER, 0.6476);
        objectiveHabitualModeShare.get(Occupation.EMPLOYED).put(HabitualMode.CAR_PASSENGER, 0.0257);
        objectiveHabitualModeShare.get(Occupation.EMPLOYED).put(HabitualMode.PT, 0.1725);
        objectiveHabitualModeShare.get(Occupation.EMPLOYED).put(HabitualMode.BIKE, 0.1135);
        objectiveHabitualModeShare.get(Occupation.EMPLOYED).put(HabitualMode.WALK, 0.0407);

        objectiveHabitualModeShare.get(Occupation.STUDENT).put(HabitualMode.CAR_DRIVER, 0.1414);
        objectiveHabitualModeShare.get(Occupation.STUDENT).put(HabitualMode.CAR_PASSENGER, 0.0662);
        objectiveHabitualModeShare.get(Occupation.STUDENT).put(HabitualMode.PT, 0.5313);
        objectiveHabitualModeShare.get(Occupation.STUDENT).put(HabitualMode.BIKE, 0.1786);
        objectiveHabitualModeShare.get(Occupation.STUDENT).put(HabitualMode.WALK, 0.0825);

//        objectiveHabitualModeShare.get(Occupation.TODDLER).putIfAbsent(Mode.CAR_DRIVER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.TODDLER).putIfAbsent(Mode.CAR_PASSENGER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.TODDLER).putIfAbsent(Mode.BUS, 0.00);
//        objectiveHabitualModeShare.get(Occupation.TODDLER).putIfAbsent(Mode.BIKE, 0.00);
//        objectiveHabitualModeShare.get(Occupation.TODDLER).putIfAbsent(Mode.WALK, 0.00);
//
//        objectiveHabitualModeShare.get(Occupation.RETIREE).putIfAbsent(Mode.CAR_DRIVER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.RETIREE).putIfAbsent(Mode.CAR_PASSENGER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.RETIREE).putIfAbsent(Mode.BUS, 0.00);
//        objectiveHabitualModeShare.get(Occupation.RETIREE).putIfAbsent(Mode.BIKE, 0.00);
//        objectiveHabitualModeShare.get(Occupation.RETIREE).putIfAbsent(Mode.WALK, 0.00);
//
//        objectiveHabitualModeShare.get(Occupation.UNEMPLOYED).putIfAbsent(Mode.CAR_DRIVER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.UNEMPLOYED).putIfAbsent(Mode.CAR_PASSENGER, 0.00);
//        objectiveHabitualModeShare.get(Occupation.UNEMPLOYED).putIfAbsent(Mode.BUS, 0.00);
//        objectiveHabitualModeShare.get(Occupation.UNEMPLOYED).putIfAbsent(Mode.BIKE, 0.00);
//        objectiveHabitualModeShare.get(Occupation.UNEMPLOYED).putIfAbsent(Mode.WALK, 0.00);
    }

    private void summarizeSimulatedResult() {

        for (Occupation occupation : Occupation.values()) {
            simulatedPopCount.put(occupation, 0);
            for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
                simulatedHabitualModeCount.get(occupation).put(habitualMode, 0);
                simulatedHabitualModeShare.get(occupation).put(habitualMode, 0.0);
                simulatedHabitualAggreModeCount.put(habitualMode, 0);
                simulatedHabitualAggreModeShare.put(habitualMode, 0.0);
            }
        }

        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()) {
                    if (person.getAge() >= 10) {
                        if (person.getOccupation().equals(Occupation.EMPLOYED) || person.getOccupation().equals(Occupation.STUDENT)) {
                            int modeCount = simulatedHabitualModeCount.get(person.getOccupation()).get(person.getHabitualMode());
                            simulatedHabitualModeCount.get(person.getOccupation()).replace(person.getHabitualMode(), modeCount + 1);
                            int popCount = simulatedPopCount.get(person.getOccupation());
                            simulatedPopCount.replace(person.getOccupation(), popCount + 1);
                            int modeAggreCount = simulatedHabitualAggreModeCount.get(person.getHabitualMode());
                            simulatedHabitualAggreModeCount.replace(person.getHabitualMode(), modeAggreCount + 1);
                        }
                    }
                }
            }
        }

        for (Occupation occupation : Occupation.values()) {
            if (occupation.equals(Occupation.EMPLOYED) || occupation.equals(Occupation.STUDENT)) {
                int popCount = simulatedPopCount.get(occupation);
                int modeCount;
                for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
                    modeCount = simulatedHabitualModeCount.get(occupation).get(habitualMode);
                    double modeShare = (double) modeCount / popCount;
                    simulatedHabitualModeShare.get(occupation).replace(habitualMode, modeShare);
                }
            }
        }

        for (HabitualMode habitualMode : HabitualMode.getHabitualModes()) {
            int popCount = simulatedPopCount.get(Occupation.EMPLOYED) + simulatedPopCount.get(Occupation.STUDENT);
            int modeCount = simulatedHabitualAggreModeCount.get(habitualMode);
            double modeShare = (double) modeCount / popCount;
            simulatedHabitualAggreModeShare.replace(habitualMode, modeShare);
        }
    }

    private void printFinalCoefficientsTable(Map<HabitualMode, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing habitual mode choice coefficient + calibration factors: " + inputFolder);
        PrintWriter pw = new PrintWriter(inputFolder);

        StringBuilder header = new StringBuilder("variable");
        for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
            header.append(",");
            header.append(habitualMode);
        }
        pw.println(header);

        for (String variableNames : finalCoefficientsTable.get(HabitualMode.PT).keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            for (HabitualMode habitualMode : HabitualMode.getHabitualModesWithoutUnknown()) {
                if (variableNames.equals("calibration_retiree") || variableNames.equals("calibration_toddler") || variableNames.equals("calibration_unemployed")) {
                    line.append(",");
                    line.append(0);
                } else {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(habitualMode).get(variableNames));
                }
            }
            pw.println(line);
        }
        pw.close();
    }
}
