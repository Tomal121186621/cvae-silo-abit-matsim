package abm.scenarios.lowEmissionZones.runner;

import abm.CheckResults;
import abm.calibration.CalibrationMuc;
import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.pop.Household;
import abm.io.input.DefaultDataReaderManager;
import abm.io.output.OutputWriter;
import abm.io.output.StatisticsPrinter;
import abm.models.ModelSetup;
import abm.models.PlanGenerator3;
import abm.properties.AbitResources;
import abm.scenarios.lowEmissionZones.ModelSetupMucLowEmissionZone;
import abm.scenarios.lowEmissionZones.models.PlanGenerator3LowEmissionZones;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.util.MitoUtil;
import de.tum.bgu.msm.util.concurrent.ConcurrentExecutor;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class RunAbitLowEmissionZones {

    static Logger logger = Logger.getLogger(RunAbitLowEmissionZones.class);


    /**
     * Runs a default implementation of the AB model
     *
     * @param args
     */
    public static void main(String[] args) throws FileNotFoundException {

        AbitResources.initializeResources(args[0]);
        AbitUtils.loadHdf5Lib();

        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());

        logger.info("Reading data");
        DataSet dataSet = new DefaultDataReaderManager().readData();

        logger.info("Creating the sub-models");
        //ModelSetup modelSetup = new ModelSetupMuc(dataSet);
        ModelSetup modelSetup = new ModelSetupMucLowEmissionZone(dataSet);

        logger.info("Generating plans");
        int threads = Runtime.getRuntime().availableProcessors();
        ConcurrentExecutor executor = ConcurrentExecutor.fixedPoolService(threads);
        Map<Integer, List<Household>> householdsByThread = new HashMap<>();

        logger.info("Running plan generator using " + threads + " threads");

        long start = System.currentTimeMillis();

        //TODO: parallelize by household not person because of vehicle assignment. Later, for joint travel/coordination destination, need to move parallelization into model steps?
        if (AbitResources.instance.getDouble("scale.factor", 1.0) >= 1){
            for (Household household : dataSet.getHouseholds().values()) {
                if (household.getPartition() == 2){
                    final int i = AbitUtils.getRandomObject().nextInt(threads);
                    householdsByThread.putIfAbsent(i, new ArrayList<>());
                    householdsByThread.get(i).add(household);
                    household.setSimulated(Boolean.TRUE);
                }
            }
        }else {
            for (Household household : dataSet.getHouseholds().values()) {
                if (AbitUtils.getRandomObject().nextDouble() < AbitResources.instance.getDouble("scale.factor", 1.0)) {
                    final int i = AbitUtils.getRandomObject().nextInt(threads);
                    householdsByThread.putIfAbsent(i, new ArrayList<>());
                    householdsByThread.get(i).add(household);
                    household.setSimulated(Boolean.TRUE);
                }
            }
        }

        for (int i = 0; i < threads; i++) {
            executor.addTaskToQueue(new PlanGenerator3LowEmissionZones(dataSet, modelSetup, i).setHouseholds(householdsByThread.get(i)));
        }

        executor.execute();

        if (Boolean.parseBoolean(AbitResources.instance.getString("model.calibration"))){
            CalibrationMuc calibrationMuc = new CalibrationMuc(dataSet);
            calibrationMuc.runCalibration();
        }

        //todo. summary (trip length frequency distribution, etc.)
        String outputFolder = AbitResources.instance.getString("base.directory") + "/output/";

        logger.info("Printing out results");
        try {

            new StatisticsPrinter(dataSet).print(outputFolder + "/distanceDistribution.csv");

        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }


        //todo. consistency check before summarizing the trip list (useful for the debugging phase, have it as false for the application later on)

        //todo. auto calibration outputs

        // TODO: new code - Yangqian
        CheckResults checkResults = new CheckResults(dataSet);
        checkResults.checkTimeConflict();
        System.out.println("Number of people with schedule conflict: "+checkResults.getNumOfPeopleWithTimeConflict());
        for (Mode mode: checkResults.getLegsWithWrongTravelTime().keySet()){
            System.out.println(mode+":"+checkResults.getLegsWithWrongTravelTime().get(mode));
        }
        checkResults.checkVehicleUse();
        System.out.println("Number of cars with overlap use: "+checkResults.getOverlapCarUse());
        checkResults.checkAccompanyTrip();
        System.out.println("Number of accompany trip without accompany in the household: "+checkResults.getAccompanyTripInconsistency());
        checkResults.checkChildTrip();
        for (Purpose purpose: checkResults.getChildTripWithoutAccompany().keySet()){
            System.out.println("Number of child trip for "+purpose+" without the accompany in the household:"+checkResults.getChildTripWithoutAccompany().get(purpose));
        }

        long end = System.currentTimeMillis();



        long time = (end - start)/1000;

        logger.info("Runtime = " + time + " Persons = " + dataSet.getPersons().size());

        logger.info("Printing out results");
        new OutputWriter(dataSet).run();
    }
}
