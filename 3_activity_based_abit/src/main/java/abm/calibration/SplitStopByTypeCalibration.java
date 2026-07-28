package abm.calibration;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.activityGeneration.splitByType.SplitByTypeModel;
import abm.models.activityGeneration.splitByType.SplitStopByTypeModel;
import abm.properties.AbitResources;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.util.HashMap;
import java.util.Map;

public class SplitStopByTypeCalibration implements ModelComponent{
    //Todo define a few calibration parameters

    static Logger logger = Logger.getLogger(SplitStopByTypeModel.class);
    Map<StopType, Double> objectiveSplitByStopType = new HashMap<>();
    Map<StopType, Double> simulatedSplitByStopType = new HashMap<>();
    //String splitStopTypeOutputFolder = AbitResources.instance.getString("act.split.stop.type.output");
    DataSet dataSet;
    private SplitStopByTypeModel splitStopByTypeCalibration;

    public SplitStopByTypeCalibration(DataSet dataSet) {
        this.dataSet = dataSet;

    }

    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated
        //boolean calibrateSplitStopByType = Boolean.parseBoolean(AbitResources.instance.getString("act.split.stop.type.calibration"));
        //splitStopByTypeCalibration = new SplitStopByTypeModel(calibrateSplitStopByType);

        //Todo: initialize all the data containers that might be needed for calibration
        objectiveSplitByStopType.putIfAbsent(StopType.BEFORE, 0.0);
        objectiveSplitByStopType.putIfAbsent(StopType.AFTER, 0.0);
        simulatedSplitByStopType.putIfAbsent(StopType.BEFORE, 0.0);
        simulatedSplitByStopType.putIfAbsent(StopType.AFTER, 0.0);
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
        logger.info("Start calibrating the split stop by type model......");

        double observedShare;
        double simulatedShare;
        double difference;


        observedShare = objectiveSplitByStopType.get(StopType.BEFORE);
        simulatedShare = simulatedSplitByStopType.get(StopType.BEFORE);
        difference = observedShare - simulatedShare;
        logger.info("Split stop by type " + "\t" + StopType.BEFORE + " difference: " + difference);

        observedShare = objectiveSplitByStopType.get(StopType.AFTER);
        simulatedShare = simulatedSplitByStopType.get(StopType.AFTER);
        difference = observedShare - simulatedShare;
        logger.info("Split stop by type " + "\t" + StopType.AFTER + " difference: " + difference);

        //Todo: loop through the calibration process until criteria are met



        //Todo: obtain the updated coefficients + calibration factors


        //Todo: print the coefficients table to input folder

    }

    private void readObjectiveValues() {
        objectiveSplitByStopType.put(StopType.BEFORE, 0.27);
        objectiveSplitByStopType.put(StopType.AFTER,0.73);
    }

    private void summarizeSimulatedResult() {
        int numStopBefore = 0;
        int numStopAfter = 0;
        int mainActStartTime = 0;
        for (Household household : dataSet.getHouseholds().values()) {
            if (household.getSimulated()) {
                for (Person person : household.getPersons()){
                    for (Tour tour : person.getPlan().getTours().values()){
                        if(tour.getActivities().size()>1){
                            for (Activity act: tour.getActivities().values()) {
                                if (act.getDiscretionaryActivityType() == null ||
                                        act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.ACCOMPANY_PRIMARY) ||
                                        act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.SHOP_PRIMARY) ||
                                        act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.OTHER_PRIMARY) ||
                                        act.getDiscretionaryActivityType().equals(DiscretionaryActivityType.RECREATION_PRIMARY)
                                ) {mainActStartTime = act.getStartTime_min();}
                            }
                            for (Activity act: tour.getActivities().values()) {
                                DiscretionaryActivityType type = act.getDiscretionaryActivityType();
                                if (type != null) {
                                    if (!(type.equals(DiscretionaryActivityType.ACCOMPANY_PRIMARY)) &&
                                            !(type.equals(DiscretionaryActivityType.SHOP_PRIMARY)) &&
                                            !(type.equals(DiscretionaryActivityType.OTHER_PRIMARY)) &&
                                            !(type.equals(DiscretionaryActivityType.RECREATION_PRIMARY))) {
                                        if(act.getStartTime_min()<mainActStartTime){numStopBefore++;
                                        }else{numStopAfter++;}
                                    }
                                }
                            }
                        }else{continue;}
                    }
                }
            }
        }
        simulatedSplitByStopType.replace(StopType.BEFORE, (double) numStopBefore/(numStopBefore+numStopAfter));
        simulatedSplitByStopType.replace(StopType.AFTER, (double) numStopAfter/(numStopBefore+numStopAfter));
    }

    private void printFinalCoefficientsTable(Map<Mode, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {

    }
}
