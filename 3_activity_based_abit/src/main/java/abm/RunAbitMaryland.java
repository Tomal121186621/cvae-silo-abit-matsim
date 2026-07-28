package abm;

import abm.data.DataSet;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.io.input.MarylandDataReaderManager;
import abm.io.output.ActivityPrinter;
import abm.io.output.LegPrinter;
import abm.io.output.PersonUseOfTimePrinter;
import abm.models.ModelSetup;
import abm.models.PlanGenerator;
import abm.models.SimpleModelSetup;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.util.MitoUtil;
import de.tum.bgu.msm.util.concurrent.ConcurrentExecutor;
import org.apache.log4j.Logger;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Hello-world runner proving the SILO -> ABIT -> activity-plans path on the Maryland calib5 population.
 *
 * Reads a SUBSET of the SILO synthetic population ({@link MarylandDataReaderManager}) and runs it through
 * the dummy-coefficient {@link SimpleModelSetup}. No Munich coefficient files, OMX skims, or zones
 * shapefile are needed. Produces activity/leg/time-use CSVs under {base.directory}/output/.
 */
public class RunAbitMaryland {

    private static final Logger logger = Logger.getLogger(RunAbitMaryland.class);

    public static void main(String[] args) {

        AbitResources.initializeResources(args[0]);
        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());

        int maxHouseholds = AbitResources.instance.getInt("max.households", 2000);
        int threads = AbitResources.instance.getInt("number.of.threads", 1);

        logger.info("Reading SILO population (cap " + maxHouseholds + " households)");
        DataSet dataSet = new MarylandDataReaderManager(maxHouseholds).readData();

        logger.info("Creating the (Simple) sub-models");
        ModelSetup modelSetup = new SimpleModelSetup(dataSet);

        logger.info("Generating plans using " + threads + " threads");
        ConcurrentExecutor executor = ConcurrentExecutor.fixedPoolService(threads);
        Map<Integer, List<Person>> personsByThread = new HashMap<>();
        int i = 0;
        for (Household household : dataSet.getHouseholds().values()) {
            for (Person person : household.getPersons()) {
                int t = i % threads;
                personsByThread.putIfAbsent(t, new ArrayList<>());
                personsByThread.get(t).add(person);
                i++;
            }
        }
        for (int t = 0; t < threads; t++) {
            executor.addTaskToQueue(new PlanGenerator(dataSet, modelSetup, t)
                    .setPersons(personsByThread.getOrDefault(t, new ArrayList<>())));
        }
        executor.execute();

        String outputFolder = AbitResources.instance.getString("base.directory") + "/output/";
        new File(outputFolder).mkdirs();

        logger.info("Printing results to " + outputFolder);
        try {
            new ActivityPrinter(dataSet).print(outputFolder + "/activities.csv");
        } catch (Exception e) {
            logger.error("ActivityPrinter failed", e);
        }
        try {
            new LegPrinter(dataSet).print(outputFolder + "/legs.csv");
        } catch (Exception e) {
            logger.error("LegPrinter failed", e);
        }
        try {
            new PersonUseOfTimePrinter(dataSet).print(outputFolder + "/use_of_time.csv");
        } catch (Exception e) {
            logger.error("PersonUseOfTimePrinter failed", e);
        }

        logger.info("DONE. persons=" + dataSet.getPersons().size());
    }
}
