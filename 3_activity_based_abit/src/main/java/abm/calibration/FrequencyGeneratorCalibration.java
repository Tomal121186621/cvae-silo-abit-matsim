package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.EmploymentStatus;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.FrequencyGeneratorModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.commons.collections.map.HashedMap;
import org.apache.log4j.Logger;


import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

import static abm.data.plans.Purpose.ACCOMPANY;


public class FrequencyGeneratorCalibration implements ModelComponent {

    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(HabitualModeChoiceCalibration.class);
    DataSet dataSet;
    private static final int MAX_ITERATION = 2_000;
    private static final double TERMINATION_THRESHOLD = 0.06;
    double stepSize = 0.8;
    Map<Purpose, Map<Integer, Double>> objectiveFrequencyShare = new HashMap<>();
    Map<Purpose, Map<Integer, Integer>> simulatedFrequencyCount = new HashMap<>();

    Map<Purpose, Map<Integer, Integer>> simulatedFrequencyCountOnTheFly = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> simulatedFrequencyShare = new HashMap<>();

    Map<Purpose, Map<Integer, Double>> simulatedFrequencyShareOnTheFly = new HashMap<>();
    Map<Purpose, Map<Integer, Double>> calibrationFactors = new HashMap<>();
    private final Map<Purpose, FrequencyGenerator> frequencyGeneratorsForCalibration = new HashMap<>();

    Map<Purpose, Map<String, Map<String, Double>>> finalCoefficientsTable = new HashMap<>();

    public FrequencyGeneratorCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    String zeroMandAccompanyCoefficientsPath = AbitResources.instance.getString("actgen.mand-ac-rr.zero.output");
    String countMandCoefficientsPath = AbitResources.instance.getString("actgen.mand.count.output");
    String countAccompanyCoefficientsPath = AbitResources.instance.getString("actgen.ac-rr.count.output");

    String countShoppingRecreationOtherCoefficientsPath = AbitResources.instance.getString("actgen.sh-re-ot.count.output");
    boolean calibrateMandatoryActGen;
    boolean calibrateDiscretionaryActGen;

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        calibrateMandatoryActGen = Boolean.parseBoolean(AbitResources.instance.getString("actgen.mand.calibration"));
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            frequencyGeneratorsForCalibration.put(purpose, new FrequencyGeneratorModel(dataSet, purpose, calibrateMandatoryActGen));
        }

        calibrateDiscretionaryActGen = Boolean.parseBoolean(AbitResources.instance.getString("actgen.disc.calibration"));
        for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
            frequencyGeneratorsForCalibration.put(purpose, new FrequencyGeneratorModel(dataSet, purpose, calibrateDiscretionaryActGen));
        }

        //Todo: initialize all the data containers that might be needed for calibration
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            objectiveFrequencyShare.putIfAbsent(purpose, new HashMap<>());
            simulatedFrequencyCount.putIfAbsent(purpose, new HashMap<>());
            simulatedFrequencyCountOnTheFly.putIfAbsent(purpose, new HashMap<>());
            simulatedFrequencyShare.putIfAbsent(purpose, new HashMap<>());
            simulatedFrequencyShareOnTheFly.putIfAbsent(purpose, new HashMap<>());
            calibrationFactors.putIfAbsent(purpose, new HashMap<>());
            finalCoefficientsTable.putIfAbsent(purpose, new HashMap<>());
            for (int freq = 0; freq <= 7; freq++) {
                objectiveFrequencyShare.get(purpose).putIfAbsent(freq, 0.0);
                simulatedFrequencyCount.get(purpose).putIfAbsent(freq, 0);
                simulatedFrequencyCountOnTheFly.get(purpose).putIfAbsent(freq, 0);
                simulatedFrequencyShare.get(purpose).putIfAbsent(freq, 0.0);
                simulatedFrequencyShareOnTheFly.get(purpose).putIfAbsent(freq, 0.0);
                calibrationFactors.get(purpose).putIfAbsent(freq, 0.0);
            }
            finalCoefficientsTable.get(purpose).putIfAbsent("zero", new HashMap<>());
            finalCoefficientsTable.get(purpose).putIfAbsent("count", new HashMap<>());
        }
        objectiveFrequencyShare.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        simulatedFrequencyCount.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        simulatedFrequencyCountOnTheFly.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        simulatedFrequencyShare.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        simulatedFrequencyShareOnTheFly.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        calibrationFactors.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        finalCoefficientsTable.putIfAbsent(Purpose.ACCOMPANY, new HashMap<>());
        for (int freq = 0; freq <= 7; freq++) {
            objectiveFrequencyShare.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0.0);
            simulatedFrequencyCount.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0);
            simulatedFrequencyCountOnTheFly.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0);
            simulatedFrequencyShare.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0.0);
            simulatedFrequencyShareOnTheFly.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0.0);
            calibrationFactors.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0.0);
        }
        finalCoefficientsTable.get(Purpose.ACCOMPANY).putIfAbsent("zero", new HashMap<>());
        finalCoefficientsTable.get(Purpose.ACCOMPANY).putIfAbsent("count", new HashMap<>());
        for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
            if (!purpose.equals(Purpose.ACCOMPANY)) {
                objectiveFrequencyShare.putIfAbsent(purpose, new HashMap<>());
                simulatedFrequencyCount.putIfAbsent(purpose, new HashMap<>());
                simulatedFrequencyCountOnTheFly.putIfAbsent(purpose, new HashMap<>());
                simulatedFrequencyShare.putIfAbsent(purpose, new HashMap<>());
                simulatedFrequencyShareOnTheFly.putIfAbsent(purpose, new HashMap<>());
                calibrationFactors.putIfAbsent(purpose, new HashMap<>());
                finalCoefficientsTable.putIfAbsent(purpose, new HashMap<>());
                for (int freq = 0; freq <= 15; freq++) {
                    objectiveFrequencyShare.get(purpose).putIfAbsent(freq, 0.0);
                    simulatedFrequencyCount.get(purpose).putIfAbsent(freq, 0);
                    simulatedFrequencyCountOnTheFly.get(purpose).putIfAbsent(freq, 0);
                    simulatedFrequencyShare.get(purpose).putIfAbsent(freq, 0.0);
                    simulatedFrequencyShareOnTheFly.get(purpose).putIfAbsent(freq, 0.0);
                    calibrationFactors.get(purpose).putIfAbsent(freq, 0.0);
                }
                finalCoefficientsTable.get(purpose).putIfAbsent("count", new HashMap<>());
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
        logger.info("Start calibrating the frequency of trip model......");

        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            logger.info("Iteration......" + iteration);
            double maxDifference = 0.0;

            if (calibrateMandatoryActGen) {
                for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                    for (int frequencies = 0; frequencies <= 7; frequencies++) {
                        double observedCountShare = objectiveFrequencyShare.get(purpose).get(frequencies);
                        double simulatedCountShare = simulatedFrequencyShare.get(purpose).get(frequencies);
                        double difference = observedCountShare - simulatedCountShare;
                        double factor = stepSize * (observedCountShare - simulatedCountShare);
                        if (frequencies == 0) {
                            factor = -1 * factor;
                        }
                        calibrationFactors.get(purpose).replace(frequencies, factor);
                        logger.info("Frequency of mandatory trip model for " + purpose.toString() + "\t" + " and " + frequencies + "\t" + " difference: " + difference);
                        if (Math.abs(difference) > maxDifference) {
                            maxDifference = Math.abs(difference);
                        }
                    }
                    ((FrequencyGeneratorModel) frequencyGeneratorsForCalibration.get(purpose)).updateCalibrationFactor(calibrationFactors.get(purpose));
                }
            }

            if (calibrateDiscretionaryActGen) {

                for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
                    if (purpose.equals(ACCOMPANY)) {
//                        double totalCountError = 0.0;
//                        for (int frequencies = 0; frequencies <= 7; frequencies++) {
//                            double observedZeroShare = objectiveFrequencyShare.get(purpose).get(frequencies);
//                            double simulatedZeroShare = simulatedFrequencyShare.get(purpose).get(frequencies);
//                            double difference = observedZeroShare - simulatedZeroShare;
//                            double factor = stepSize * (observedZeroShare - simulatedZeroShare);
//                            if (frequencies == 0) {
//                                factor = -1 * factor;
//                            } else {
//                                totalCountError += Math.abs(difference);
//                                factor = -1 * factor;
//                            }
//                           calibrationFactors.get(purpose).replace(frequencies, factor);
//                            logger.info("Frequency of mandatory trip model for " + purpose.toString() + "\t" + " and " + frequencies + "\t" + " difference: " + difference);
//                            if (totalCountError > maxDifference) {
//                                maxDifference = totalCountError;
//                            }
//                        }
//                        logger.info("Total count error for " + purpose.toString() + "\t" + " difference: " + totalCountError);
//                        ((FrequencyGeneratorModel) frequencyGeneratorsForCalibration.get(purpose)).updateCalibrationFactor(calibrationFactors.get(purpose));
                    }
                    else {
                        for (int frequencies = 0; frequencies <= 15; frequencies++) {
                            double observedCountShare = objectiveFrequencyShare.get(purpose).get(frequencies);
                            double simulatedCountShare = simulatedFrequencyShare.get(purpose).get(frequencies);
                            double difference = observedCountShare - simulatedCountShare;
                            double factor = -1 * stepSize * (observedCountShare - simulatedCountShare);
                            calibrationFactors.get(purpose).replace(frequencies, factor);
                            logger.info("Frequency of mandatory trip model for " + purpose.toString() + "\t" + " and " + frequencies + "\t" + " difference: " + difference);
                            if (Math.abs(difference) > maxDifference) {
                                maxDifference = Math.abs(difference);
                            }
                        }
                        ((FrequencyGeneratorModel) frequencyGeneratorsForCalibration.get(purpose)).updateCalibrationFactor(calibrationFactors.get(purpose));
                    }
                }
            }


            for (Person person : dataSet.getPersons().values()) {
                if (person.getHousehold().getSimulated()) {
                    for (Purpose purpose : Purpose.getAllPurposes()) {

                        int numOfAct = frequencyGeneratorsForCalibration.get(purpose).calculateNumberOfActivitiesPerWeek(person, purpose);

                        if (purpose.equals(Purpose.WORK) && person.getAge() <= 70 && person.getAge() >= 15) {
                            int simluatedWorkCount = simulatedFrequencyCountOnTheFly.get(Purpose.WORK).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.WORK).replace(numOfAct, simluatedWorkCount + 1);
                        }
                        if (purpose.equals(Purpose.EDUCATION) && person.getAge() >= 10 && person.getOccupation().equals(Occupation.STUDENT)) {
                            int simluatedEducationCount = simulatedFrequencyCountOnTheFly.get(Purpose.EDUCATION).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.EDUCATION).replace(numOfAct, simluatedEducationCount + 1);
                        }
                        if (purpose.equals(Purpose.ACCOMPANY)) {
                            int simluatedAccompanyCount = simulatedFrequencyCountOnTheFly.get(Purpose.ACCOMPANY).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.ACCOMPANY).replace(numOfAct, simluatedAccompanyCount + 1);
                        }
                        if (purpose.equals(Purpose.RECREATION)) {
                            int simluatedRecreationCount = simulatedFrequencyCountOnTheFly.get(Purpose.RECREATION).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.RECREATION).replace(numOfAct, simluatedRecreationCount + 1);
                        }
                        if (purpose.equals(Purpose.OTHER)) {
                            int simluatedOtherCount = simulatedFrequencyCountOnTheFly.get(Purpose.OTHER).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.OTHER).replace(numOfAct, simluatedOtherCount + 1);
                        }
                        if (purpose.equals(Purpose.SHOPPING)) {
                            int simluatedShoppingCount = simulatedFrequencyCountOnTheFly.get(Purpose.SHOPPING).get(numOfAct);
                            simulatedFrequencyCountOnTheFly.get(Purpose.SHOPPING).replace(numOfAct, simluatedShoppingCount + 1);
                        }
                    }
                }
            }

            for (Purpose purpose : Purpose.getAllPurposes()) {
                if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION) || purpose.equals(Purpose.ACCOMPANY)) {
                    int totalCount = 0;
                    for (int freq = 0; freq <= 7; freq++) {
                        totalCount += simulatedFrequencyCountOnTheFly.get(purpose).get(freq);
                    }
                    for (int freq = 0; freq <= 7; freq++) {
                        double share = ((double) simulatedFrequencyCountOnTheFly.get(purpose).get(freq)) / ((double) totalCount);
                        simulatedFrequencyShare.get(purpose).replace(freq, share);
                    }
                } else {
                    int totalCount = 0;
                    for (int freq = 0; freq <= 15; freq++) {
                        totalCount += simulatedFrequencyCountOnTheFly.get(purpose).get(freq);
                    }
                    for (int freq = 0; freq <= 15; freq++) {
                        double share = ((double) simulatedFrequencyCountOnTheFly.get(purpose).get(freq)) / ((double) totalCount);
                        simulatedFrequencyShare.get(purpose).replace(freq, share);
                    }
                }
            }

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            } else {
                logger.info("MAX Diff: " + maxDifference);
            }


            //Reset the simulated frequency count on the fly
            for (Purpose purpose : Purpose.getAllPurposes()) {
                if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION) || purpose.equals(Purpose.ACCOMPANY)) {
                    for (int freq = 0; freq <= 7; freq++) {
                        simulatedFrequencyCountOnTheFly.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0);
                        simulatedFrequencyShare.get(Purpose.ACCOMPANY).putIfAbsent(freq, 0.0);
                    }
                } else {
                    for (int freq = 0; freq <= 15; freq++) {
                        simulatedFrequencyCountOnTheFly.get(purpose).putIfAbsent(freq, 0);
                        simulatedFrequencyShare.get(purpose).putIfAbsent(freq, 0.0);
                    }
                }
            }

        }
        logger.info("Finished the calibration of activity frequency generation model.");


        //Todo: obtain the updated coefficients + calibration factors
        for (Purpose purpose : Purpose.getAllPurposes()) {
            if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION) || purpose.equals(ACCOMPANY)) {
                finalCoefficientsTable.get(purpose).replace("zero", ((FrequencyGeneratorModel) (frequencyGeneratorsForCalibration.get(purpose))).obtainZeroCoefficients());
                if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION)) {
                    finalCoefficientsTable.get(purpose).replace("count", ((FrequencyGeneratorModel) (frequencyGeneratorsForCalibration.get(purpose))).obtainCountWorkEducationCoefficients());
                } else {
                    finalCoefficientsTable.get(purpose).replace("count", ((FrequencyGeneratorModel) (frequencyGeneratorsForCalibration.get(purpose))).obtainAccompanyCountCoefficients());
                }
            } else {
                finalCoefficientsTable.get(purpose).replace("count", ((FrequencyGeneratorModel) (frequencyGeneratorsForCalibration.get(purpose))).obtainCountCoefficients());
            }
        }

        //Todo: print the coefficients table to input folder
        try {
            printFinalCoefficientsTable(finalCoefficientsTable);
        } catch (FileNotFoundException e) {
            System.err.println("Output path of the coefficient table is not correct.");
        }

    }

    private void readObjectiveValues() {
        objectiveFrequencyShare.get(Purpose.WORK).put(0, 0.3738);
        objectiveFrequencyShare.get(Purpose.WORK).put(1, 0.0351);
        objectiveFrequencyShare.get(Purpose.WORK).put(2, 0.0456);
        objectiveFrequencyShare.get(Purpose.WORK).put(3, 0.0633);
        objectiveFrequencyShare.get(Purpose.WORK).put(4, 0.1218);
        objectiveFrequencyShare.get(Purpose.WORK).put(5, 0.3219);
        objectiveFrequencyShare.get(Purpose.WORK).put(6, 0.0319);
        objectiveFrequencyShare.get(Purpose.WORK).put(7, 0.0066);

        objectiveFrequencyShare.get(Purpose.EDUCATION).put(0, 0.2085);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(1, 0.0470);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(2, 0.0674);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(3, 0.0596);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(4, 0.1520);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(5, 0.4498);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(6, 0.0141);
        objectiveFrequencyShare.get(Purpose.EDUCATION).put(7, 0.0016);

        objectiveFrequencyShare.get(ACCOMPANY).put(0, 0.6215);
        objectiveFrequencyShare.get(ACCOMPANY).put(1, 0.1743);
        objectiveFrequencyShare.get(ACCOMPANY).put(2, 0.0778);
        objectiveFrequencyShare.get(ACCOMPANY).put(3, 0.0396);
        objectiveFrequencyShare.get(ACCOMPANY).put(4, 0.0307);
        objectiveFrequencyShare.get(ACCOMPANY).put(5, 0.0407);
        objectiveFrequencyShare.get(ACCOMPANY).put(6, 0.0135);
        objectiveFrequencyShare.get(ACCOMPANY).put(7, 0.0019);

        objectiveFrequencyShare.get(Purpose.RECREATION).put(0, 0.155);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(1, 0.190);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(2, 0.171);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(3, 0.150);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(4, 0.111);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(5, 0.084);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(6, 0.054);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(7, 0.034);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(8, 0.017);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(9, 0.012);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(10, 0.010);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(11, 0.003);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(12, 0.004);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(13, 0.003);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(14, 0.001);
        objectiveFrequencyShare.get(Purpose.RECREATION).put(15, 0.001);

        objectiveFrequencyShare.get(Purpose.SHOPPING).put(0, 0.206);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(1, 0.209);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(2, 0.201);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(3, 0.142);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(4, 0.092);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(5, 0.058);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(6, 0.039);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(7, 0.019);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(8, 0.015);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(9, 0.008);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(10, 0.008);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(11, 0.002);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(12, 0.001);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(13, 0.000);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(14, 0.000);
        objectiveFrequencyShare.get(Purpose.SHOPPING).put(15, 0.000);

        objectiveFrequencyShare.get(Purpose.OTHER).put(0, 0.372);
        objectiveFrequencyShare.get(Purpose.OTHER).put(1, 0.268);
        objectiveFrequencyShare.get(Purpose.OTHER).put(2, 0.157);
        objectiveFrequencyShare.get(Purpose.OTHER).put(3, 0.093);
        objectiveFrequencyShare.get(Purpose.OTHER).put(4, 0.052);
        objectiveFrequencyShare.get(Purpose.OTHER).put(5, 0.026);
        objectiveFrequencyShare.get(Purpose.OTHER).put(6, 0.016);
        objectiveFrequencyShare.get(Purpose.OTHER).put(7, 0.007);
        objectiveFrequencyShare.get(Purpose.OTHER).put(8, 0.003);
        objectiveFrequencyShare.get(Purpose.OTHER).put(9, 0.002);
        objectiveFrequencyShare.get(Purpose.OTHER).put(10, 0.004);
        objectiveFrequencyShare.get(Purpose.OTHER).put(11, 0.000);
        objectiveFrequencyShare.get(Purpose.OTHER).put(12, 0.000);
        objectiveFrequencyShare.get(Purpose.OTHER).put(13, 0.000);
        objectiveFrequencyShare.get(Purpose.OTHER).put(14, 0.000);
        objectiveFrequencyShare.get(Purpose.OTHER).put(15, 0.000);
    }

    private void summarizeSimulatedResult() {
        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                int numberDaysOfWorkPerWeek = 0;
                int numberDaysOfEducationPerWeek = 0;
                int numberDaysOfAccompanyPerWeek = 0;
                int numberActsOfRecreationPerWeek = 0;
                int numberActsOfOtherPerWeek = 0;
                int numberActsOfShoppingPerWeek = 0;

                for (Person person : household.getPersons()) {
                    numberDaysOfWorkPerWeek = 0;
                    numberDaysOfEducationPerWeek = 0;
                    numberDaysOfAccompanyPerWeek = 0;
                    numberActsOfRecreationPerWeek = 0;
                    numberActsOfOtherPerWeek = 0;
                    numberActsOfShoppingPerWeek = 0;
                    if (person.getPlan() != null) {
                        Plan plan = person.getPlan();
                        for (Tour tour : plan.getTours().values()) {
                            for (Activity act : tour.getActivities().values()) {

                                if (person.getAge() <= 70 && person.getAge() >= 15 && act.getPurpose().equals(Purpose.WORK) && numberDaysOfWorkPerWeek < 7) {
                                    numberDaysOfWorkPerWeek += 1;
                                }
                                if (person.getAge() >= 10 && person.getOccupation().equals(Occupation.STUDENT) && act.getPurpose().equals(Purpose.EDUCATION) && numberDaysOfEducationPerWeek < 7) {
                                    numberDaysOfEducationPerWeek += 1;
                                }
                                if (act.getPurpose().equals(Purpose.ACCOMPANY) && numberDaysOfAccompanyPerWeek < 7) {
                                    numberDaysOfAccompanyPerWeek += 1;
                                }
                                if (act.getPurpose().equals(Purpose.RECREATION) && numberActsOfRecreationPerWeek < 15) {
                                    numberActsOfRecreationPerWeek += 1;
                                }
                                if (act.getPurpose().equals(Purpose.OTHER) && numberActsOfOtherPerWeek < 15) {
                                    numberActsOfOtherPerWeek += 1;
                                }
                                if (act.getPurpose().equals(Purpose.SHOPPING) && numberActsOfShoppingPerWeek < 15) {
                                    numberActsOfShoppingPerWeek += 1;
                                }
                            }
                        }

                        for (Activity unfittedActs : plan.getUnmetActivities().values()) {
                            if (person.getAge() <= 70 && person.getAge() >= 15 && unfittedActs.getPurpose().equals(Purpose.WORK)) {
                                numberDaysOfWorkPerWeek += 1;
                            }
                            if (person.getAge() >= 10 && person.getOccupation().equals(Occupation.STUDENT) && unfittedActs.getPurpose().equals(Purpose.EDUCATION)) {
                                numberDaysOfEducationPerWeek += 1;
                            }
                            if (unfittedActs.getPurpose().equals(Purpose.ACCOMPANY)) {
                                numberDaysOfAccompanyPerWeek += 1;
                            }
                            if (unfittedActs.getPurpose().equals(Purpose.RECREATION)) {
                                numberActsOfRecreationPerWeek += 1;
                            }
                            if (unfittedActs.getPurpose().equals(Purpose.OTHER)) {
                                numberActsOfOtherPerWeek += 1;
                            }
                            if (unfittedActs.getPurpose().equals(Purpose.SHOPPING)) {
                                numberActsOfShoppingPerWeek += 1;
                            }
                        }

                    }

                    if (numberDaysOfWorkPerWeek > 7 || numberDaysOfEducationPerWeek > 7 || numberDaysOfAccompanyPerWeek > 7 ||
                            numberActsOfOtherPerWeek > 15 || numberActsOfRecreationPerWeek > 15 || numberActsOfShoppingPerWeek > 15) {
                        System.out.println("scheck here");
                    }


                    if (person.getAge() <= 70 && person.getAge() >= 15) {
                        int simluatedWorkCount = simulatedFrequencyCount.get(Purpose.WORK).get(numberDaysOfWorkPerWeek);
                        simulatedFrequencyCount.get(Purpose.WORK).replace(numberDaysOfWorkPerWeek, simluatedWorkCount + 1);
                    }
                    if (person.getAge() >= 10 && person.getOccupation().equals(Occupation.STUDENT)) {
                        int simluatedEducationCount = simulatedFrequencyCount.get(Purpose.EDUCATION).get(numberDaysOfEducationPerWeek);
                        simulatedFrequencyCount.get(Purpose.EDUCATION).replace(numberDaysOfEducationPerWeek, simluatedEducationCount + 1);
                    }
                    int simluatedAccompanyCount = simulatedFrequencyCount.get(Purpose.ACCOMPANY).get(numberDaysOfAccompanyPerWeek);
                    simulatedFrequencyCount.get(Purpose.ACCOMPANY).replace(numberDaysOfAccompanyPerWeek, simluatedAccompanyCount + 1);
                    int simluatedRecreationCount = simulatedFrequencyCount.get(Purpose.RECREATION).get(numberActsOfRecreationPerWeek);
                    simulatedFrequencyCount.get(Purpose.RECREATION).replace(numberActsOfRecreationPerWeek, simluatedRecreationCount + 1);
                    int simluatedOtherCount = simulatedFrequencyCount.get(Purpose.OTHER).get(numberActsOfOtherPerWeek);
                    simulatedFrequencyCount.get(Purpose.OTHER).replace(numberActsOfOtherPerWeek, simluatedOtherCount + 1);
                    int simluatedShoppingCount = simulatedFrequencyCount.get(Purpose.SHOPPING).get(numberActsOfShoppingPerWeek);
                    simulatedFrequencyCount.get(Purpose.SHOPPING).replace(numberActsOfShoppingPerWeek, simluatedShoppingCount + 1);
                }
            }
        }

        for (Purpose purpose : Purpose.getAllPurposes()) {
            if (purpose.equals(Purpose.WORK) || purpose.equals(Purpose.EDUCATION) || purpose.equals(Purpose.ACCOMPANY)) {
                int totalCount = 0;
                for (int freq = 0; freq <= 7; freq++) {
                    totalCount += simulatedFrequencyCount.get(purpose).get(freq);
                }
                for (int freq = 0; freq <= 7; freq++) {
                    double share = ((double) simulatedFrequencyCount.get(purpose).get(freq)) / ((double) totalCount);
                    simulatedFrequencyShare.get(purpose).replace(freq, share);
                }
            } else {
                int totalCount = 0;
                for (int freq = 0; freq <= 15; freq++) {
                    totalCount += simulatedFrequencyCount.get(purpose).get(freq);
                }
                for (int freq = 0; freq <= 15; freq++) {
                    double share = ((double) simulatedFrequencyCount.get(purpose).get(freq)) / ((double) totalCount);
                    simulatedFrequencyShare.get(purpose).replace(freq, share);
                }
            }
        }
    }

    private void printFinalCoefficientsTable(Map<Purpose, Map<String, Map<String, Double>>> finalCoefficientsTable) throws FileNotFoundException {

        logger.info("Writing act frequency coefficient + calibration factors: " + zeroMandAccompanyCoefficientsPath);
        PrintWriter pw = new PrintWriter(zeroMandAccompanyCoefficientsPath);

        StringBuilder header = new StringBuilder("variable");
        for (Purpose purpose : Purpose.getAllPurposes()) {
            if (!purpose.equals(Purpose.SHOPPING) && !purpose.equals(Purpose.RECREATION) && !purpose.equals(Purpose.OTHER)) {
                header.append(",");
                header.append(purpose.toString().toLowerCase());
            }
        }
        pw.println(header);

        for (String variableNames : finalCoefficientsTable.get(Purpose.WORK).get("zero").keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            for (Purpose purpose : Purpose.getAllPurposes()) {
                if (!purpose.equals(Purpose.SHOPPING) && !purpose.equals(Purpose.RECREATION) && !purpose.equals(Purpose.OTHER)) {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(purpose).get("zero").get(variableNames));
                }
            }
            pw.println(line);
        }
        pw.close();

        logger.info("Writing act frequency coefficient + calibration factors: " + countMandCoefficientsPath);
        PrintWriter pww = new PrintWriter(countMandCoefficientsPath);

        StringBuilder headerr = new StringBuilder("variable");
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            headerr.append(",");
            headerr.append(purpose.toString().toLowerCase());
        }
        pww.println(headerr);

        for (String variableNames : finalCoefficientsTable.get(Purpose.WORK).get("count").keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            for (Purpose purpose : Purpose.getMandatoryPurposes()) {
                line.append(",");
                line.append(finalCoefficientsTable.get(purpose).get("count").get(variableNames));
            }
            pww.println(line);
        }
        pww.close();


        logger.info("Writing act frequency coefficient + calibration factors: " + countAccompanyCoefficientsPath);
        PrintWriter pwww = new PrintWriter(countAccompanyCoefficientsPath);

        StringBuilder headerrr = new StringBuilder("variable");

        headerrr.append(",");
        headerrr.append(Purpose.ACCOMPANY.toString().toLowerCase());

        pwww.println(headerrr);

        for (String variableNames : finalCoefficientsTable.get(Purpose.ACCOMPANY).get("count").keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            line.append(",");
            line.append(finalCoefficientsTable.get(Purpose.ACCOMPANY).get("count").get(variableNames));
            pwww.println(line);
        }
        pwww.close();


        logger.info("Writing act frequency coefficient + calibration factors: " + countShoppingRecreationOtherCoefficientsPath);
        PrintWriter pwwww = new PrintWriter(countShoppingRecreationOtherCoefficientsPath);

        StringBuilder headerrrr = new StringBuilder("variable");
        for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
            if (!purpose.equals(Purpose.ACCOMPANY)) {
                headerrrr.append(",");
                headerrrr.append(purpose.toString().toLowerCase());
            }
        }
        pwwww.println(headerrrr);

        for (String variableNames : finalCoefficientsTable.get(Purpose.SHOPPING).get("count").keySet()) {
            StringBuilder line = new StringBuilder(variableNames);
            for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
                if (!purpose.equals(Purpose.ACCOMPANY)) {
                    line.append(",");
                    line.append(finalCoefficientsTable.get(purpose).get("count").get(variableNames));
                }
            }
            pwwww.println(line);
        }
        pwwww.close();
    }
}
