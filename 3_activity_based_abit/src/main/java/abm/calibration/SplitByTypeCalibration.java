package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.activityGeneration.splitByType.SplitByTypeModel;
import abm.properties.AbitResources;

import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

public class SplitByTypeCalibration implements ModelComponent{
    //Todo define a few calibration parameters
    static Logger logger = Logger.getLogger(SplitByTypeModel.class);
    private static final int MAX_ITERATION = 2_000_000;
    private static final double TERMINATION_THRESHOLD = 0.01;
    double stepSize = 10;
    String ontoMandInputFolder = AbitResources.instance.getString("act.split.type.onto.mand.output");
    String ontoDiscInputFolder = AbitResources.instance.getString("act.split.type.onto.disc.output");
    DataSet dataSet;
    Map<DiscretionaryActivityType, Double> objectiveSplitByType = new HashMap<>();
    Map<DiscretionaryActivityType, Double> simulatedSplitByType = new HashMap<>();
    Map<DiscretionaryActivityType, Double> calibrationFactors = new HashMap<>();

    private SplitByTypeModel splitByTypeCalibration;

    public SplitByTypeCalibration(DataSet dataSet) {
        this.dataSet = dataSet;
    }
    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        boolean calibrateSplitByType = Boolean.parseBoolean(AbitResources.instance.getString("act.split.type.calibration"));
        splitByTypeCalibration = new SplitByTypeModel(dataSet, calibrateSplitByType);

        //Todo: initialize all the data containers that might be needed for calibration

        objectiveSplitByType.putIfAbsent(DiscretionaryActivityType.ON_MANDATORY_TOUR, 0.0);
        simulatedSplitByType.putIfAbsent(DiscretionaryActivityType.ON_MANDATORY_TOUR, 0.0);
        calibrationFactors.putIfAbsent(DiscretionaryActivityType.ON_MANDATORY_TOUR, 0.0);
        for (DiscretionaryActivityType activityType : DiscretionaryActivityType.getDiscretionaryOntoDiscretionaryTypes()) {
            objectiveSplitByType.putIfAbsent(activityType, 0.0);
            simulatedSplitByType.putIfAbsent(activityType, 0.0);
            calibrationFactors.putIfAbsent(activityType, 0.0);
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
        logger.info("Start calibrating the split by type model......");
        //Todo: loop through the calibration process until criteria are met
        for (int iteration = 0; iteration < MAX_ITERATION; iteration++) {
            double maxDifference = 0.0;

            double observedShare;
            double simulatedShare;
            double difference;
            double factor;

            // for model that splits discretionary acts to be on mandatory tours or NOT on mandatory tours
            observedShare = objectiveSplitByType.get(DiscretionaryActivityType.ON_MANDATORY_TOUR);
            simulatedShare = simulatedSplitByType.get(DiscretionaryActivityType.ON_MANDATORY_TOUR);
            difference = observedShare - simulatedShare;
            factor = stepSize * (observedShare - simulatedShare);

            calibrationFactors.replace(DiscretionaryActivityType.ON_MANDATORY_TOUR, factor);
            logger.info("Split by type " + "\t" + DiscretionaryActivityType.ON_MANDATORY_TOUR + " difference: " + difference);
            if (Math.abs(difference) > maxDifference) {
                maxDifference = Math.abs(difference);
            }


            //for models splitting discretionary acts onto discretionary tours
            for (DiscretionaryActivityType activityType : DiscretionaryActivityType.getDiscretionaryOntoDiscretionaryTypes()) {
                observedShare = objectiveSplitByType.get(activityType);
                simulatedShare = simulatedSplitByType.get(activityType);
                difference = observedShare - simulatedShare;
                factor = stepSize * (observedShare - simulatedShare);

                calibrationFactors.replace(activityType, factor);
                logger.info("Split by type " + "\t" + activityType + " difference: " + difference);
                if (Math.abs(difference) > maxDifference) {
                    maxDifference = Math.abs(difference);
                }

            }

            if (maxDifference <= TERMINATION_THRESHOLD) {
                break;
            }

            splitByTypeCalibration.updateCalibrationFactor(calibrationFactors);

            dataSet.getHouseholds().values().parallelStream().filter(Household::getSimulated)
                    .flatMap(household -> household.getPersons().stream())
                    .flatMap(person -> person.getPlan().getTours().values().stream())
                    .flatMap(tour -> tour.getActivities().values().stream())
                    .filter(act -> act.getDiscretionaryActivityType()!=null)
                    .forEach(a -> {
                        splitByTypeCalibration.assignActType(a,a.getPerson());
                    });

            assignActTypeForDiscretionaryTourActs(dataSet, Purpose.ACCOMPANY);
            assignActTypeForDiscretionaryTourActs(dataSet, Purpose.SHOPPING);
            assignActTypeForDiscretionaryTourActs(dataSet, Purpose.OTHER);
            assignActTypeForDiscretionaryTourActs(dataSet, Purpose.RECREATION);

            summarizeSimulatedResult();

        }


        //Todo: obtain the updated coefficients + calibration factors
        Map<String, Double> finalSplitOntoMandatoryCoefficientsTable = splitByTypeCalibration.obtainSplitOntoMandatoryCoefficientsTable();
        Map<DiscretionaryActivityType, Map<String, Double>> finalSplitOntoDiscretionaryCoefficientsTable = splitByTypeCalibration.obtainSplitOntoDiscretionaryCoefficientsTable();

        //Todo: print the coefficients table to input folder
        try{
            printSplitOntoMandatoryFinalCoefficientsTable(finalSplitOntoMandatoryCoefficientsTable);
            printSplitOntoDiscretionaryFinalCoefficientsTable(finalSplitOntoDiscretionaryCoefficientsTable);
        }catch(FileNotFoundException e){
            System.err.println("Output path of the coefficient table is not correct.");
        }
    }

    private void assignActTypeForDiscretionaryTourActs(DataSet dataSet, Purpose purpose) {
        dataSet.getHouseholds().values().parallelStream()
                .filter(Household::getSimulated)
                .flatMap(household -> household.getPersons().stream())
                .flatMap(person -> person.getPlan().getTours().values().stream())
                .flatMap(tour -> tour.getActivities().values().stream())
                .filter(act -> act.getPurpose().equals(purpose) && act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.ON_DISCRETIONARY_TOUR))
                .forEach(a -> {
                    splitByTypeCalibration.assignActTypeForDiscretionaryTourActs(a, a.getPerson(),
                            (int) a.getPerson().getPlan().getTours().values().stream()
                                    .flatMap(tour -> tour.getActivities().values().stream())
                                    .filter(act -> act.getPurpose().equals(purpose) && act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.ON_DISCRETIONARY_TOUR))
                                    .count());
                });
    }

    private void readObjectiveValues() {
        objectiveSplitByType.put(DiscretionaryActivityType.ON_MANDATORY_TOUR, 0.191987);
        objectiveSplitByType.put(DiscretionaryActivityType.ACCOMPANY_ON_ACCOMPANY, 0.135349);
        objectiveSplitByType.put(DiscretionaryActivityType.SHOP_ON_ACCOMPANY, 0.058427);
        objectiveSplitByType.put(DiscretionaryActivityType.SHOP_ON_SHOP, 0.113881);
        objectiveSplitByType.put(DiscretionaryActivityType.OTHER_ON_ACCOMPANY, 0.050158);
        objectiveSplitByType.put(DiscretionaryActivityType.OTHER_ON_SHOP, 0.172274);
        objectiveSplitByType.put(DiscretionaryActivityType.OTHER_ON_OTHER, 0.057610);
        objectiveSplitByType.put(DiscretionaryActivityType.RECREATION_ON_ACCOMPANY, 0.046020);
        objectiveSplitByType.put(DiscretionaryActivityType.RECREATION_ON_SHOP, 0.087200);
        objectiveSplitByType.put(DiscretionaryActivityType.RECREATION_ON_OTHER, 0.042793);
        objectiveSplitByType.put(DiscretionaryActivityType.RECREATION_ON_RECREATION, 0.061117);
    }

    private void summarizeSimulatedResult() {

        int numActOnMandTour = 0;
        int numAccompanyPrimary = 0;
        int numShopPrimary = 0;
        int numOtherPrimary = 0;
        int numRecreationPrimary = 0;
        int numAccompanyOnAccompany = 0;
        int numShopOnAccompany = 0;
        int numShopOnShop = 0;
        int numOtherOnAccompany = 0;
        int numOtherOnShop = 0;
        int numOtherOnOther = 0;
        int numRecreationOnAccompany = 0;
        int numRecreationOnShop = 0;
        int numRecreationOnOther = 0;
        int numRecreationOnRecreation = 0;
        int numDiscretionaryAct = 0;
        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()){

                    for (Tour tour : person.getPlan().getTours().values()){
                        for (Activity act: tour.getActivities().values()) {
                            if(act.getDiscretionaryActivityType() != null) {
                                numDiscretionaryAct++;}

                            DiscretionaryActivityType type = act.getDiscretionaryActivityType();

                            if (type != null) {
                                switch (type) {
                                    case ON_MANDATORY_TOUR:
                                        numActOnMandTour++;
                                        break;
                                    case ACCOMPANY_PRIMARY:
                                        numAccompanyPrimary++;
                                        break;
                                    case SHOP_PRIMARY:
                                        numShopPrimary++;
                                        break;
                                    case OTHER_PRIMARY:
                                        numOtherPrimary++;
                                        break;
                                    case RECREATION_PRIMARY:
                                        numRecreationPrimary++;
                                        break;
                                    case ACCOMPANY_ON_ACCOMPANY:
                                        numAccompanyOnAccompany++;
                                        break;
                                    case SHOP_ON_ACCOMPANY:
                                        numShopOnAccompany++;
                                        break;
                                    case SHOP_ON_SHOP:
                                        numShopOnShop++;
                                        break;
                                    case OTHER_ON_ACCOMPANY:
                                        numOtherOnAccompany++;
                                        break;
                                    case OTHER_ON_SHOP:
                                        numOtherOnShop++;
                                        break;
                                    case OTHER_ON_OTHER:
                                        numOtherOnOther++;
                                        break;
                                    case RECREATION_ON_ACCOMPANY:
                                        numRecreationOnAccompany++;
                                        break;
                                    case RECREATION_ON_SHOP:
                                        numRecreationOnShop++;
                                        break;
                                    case RECREATION_ON_OTHER:
                                        numRecreationOnOther++;
                                        break;
                                    case RECREATION_ON_RECREATION:
                                        numRecreationOnRecreation++;
                                        break;
                                    // Add more cases as needed
                                    default:
                                        // Handle other cases or do nothing
                                }
                            }

                        }
                    }
                }
            }
        }

        simulatedSplitByType.replace(DiscretionaryActivityType.ON_MANDATORY_TOUR, (double) numActOnMandTour/numDiscretionaryAct );
        simulatedSplitByType.replace(DiscretionaryActivityType.ACCOMPANY_ON_ACCOMPANY, (double) numAccompanyOnAccompany/(numAccompanyPrimary+numAccompanyOnAccompany) );
        simulatedSplitByType.replace(DiscretionaryActivityType.SHOP_ON_ACCOMPANY, (double) numShopOnAccompany/(numShopOnAccompany+numShopOnShop+numShopPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.SHOP_ON_SHOP, (double)  numShopOnShop/(numShopOnAccompany+numShopOnShop+numShopPrimary));
        simulatedSplitByType.replace(DiscretionaryActivityType.OTHER_ON_ACCOMPANY, (double) numOtherOnAccompany/(numOtherOnAccompany+numOtherOnShop+numOtherOnOther+numOtherPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.OTHER_ON_SHOP, (double) numOtherOnShop/(numOtherOnAccompany+numOtherOnShop+numOtherOnOther+numOtherPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.OTHER_ON_OTHER, (double) numOtherOnOther/(numOtherOnAccompany+numOtherOnShop+numOtherOnOther+numOtherPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.RECREATION_ON_ACCOMPANY, (double) numRecreationOnAccompany/(numRecreationOnAccompany+numRecreationOnShop+numRecreationOnOther+numRecreationOnRecreation+numRecreationPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.RECREATION_ON_SHOP, (double) numRecreationOnShop/(numRecreationOnAccompany+numRecreationOnShop+numRecreationOnOther+numRecreationOnRecreation+numRecreationPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.RECREATION_ON_OTHER, (double) numRecreationOnOther/(numRecreationOnAccompany+numRecreationOnShop+numRecreationOnOther+numRecreationOnRecreation+numRecreationPrimary) );
        simulatedSplitByType.replace(DiscretionaryActivityType.RECREATION_ON_RECREATION, (double) numRecreationOnRecreation/(numRecreationOnAccompany+numRecreationOnShop+numRecreationOnOther+numRecreationOnRecreation+numRecreationPrimary) );

    }

    public void printSplitOntoMandatoryFinalCoefficientsTable(Map<String, Double> finalSplitOntoMandatoryCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing split onto mandatory model coefficients + calibration factors: " + ontoMandInputFolder);
        PrintWriter pw = new PrintWriter(ontoMandInputFolder);

        StringBuilder header = new StringBuilder("variable");
        header.append(",");
        header.append("discAllActSplit");

        pw.println(header);

        for (String variableNames : finalSplitOntoMandatoryCoefficientsTable.keySet()){
            StringBuilder line = new StringBuilder(variableNames);
            line.append(",");
            line.append(finalSplitOntoMandatoryCoefficientsTable.get(variableNames));
            pw.println(line);
        }
        pw.close();
    }

    public void printSplitOntoDiscretionaryFinalCoefficientsTable(Map<DiscretionaryActivityType, Map<String, Double>> finalSplitOntoDiscretionaryCoefficientsTable) throws FileNotFoundException {
        logger.info("Writing split onto discretionary coefficients + calibration factors: " + ontoDiscInputFolder);
        PrintWriter pw = new PrintWriter(ontoDiscInputFolder);

        StringBuilder header = new StringBuilder("variable");
        for (DiscretionaryActivityType activityType : DiscretionaryActivityType.getDiscretionaryOntoDiscretionaryTypes()){
            header.append(",");
            header.append(activityType.toString().toLowerCase());
        }
        pw.println(header);


        for (String variableNames : finalSplitOntoDiscretionaryCoefficientsTable.get(DiscretionaryActivityType.ACCOMPANY_ON_ACCOMPANY).keySet()){
            StringBuilder line = new StringBuilder(variableNames);
            for (DiscretionaryActivityType activityType : DiscretionaryActivityType.getDiscretionaryOntoDiscretionaryTypes()){
                line.append(",");
                line.append(finalSplitOntoDiscretionaryCoefficientsTable.get(activityType).get(variableNames));
            }
            pw.println(line);
        }
        pw.close();
    }
}
