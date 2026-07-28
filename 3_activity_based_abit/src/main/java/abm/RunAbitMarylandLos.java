package abm;

import abm.data.DataSet;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.io.input.MarylandLosDataReader;
import abm.io.output.ActivityPrinter;
import abm.io.output.LegPrinter;
import abm.models.ModelSetup;
import abm.models.ModelSetupMaryland;
import abm.models.PlanGenerator;
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
 * CALIBRATE(RTS) -> RUN(SILO calib5 + real LOS) -> single-day activity plans.
 * Uses {@link MarylandLosDataReader} (real zones/skims/coords, county subset) and
 * {@link ModelSetupMaryland} (RTS-empirical daily models).
 */
public class RunAbitMarylandLos {

    private static final Logger logger = Logger.getLogger(RunAbitMarylandLos.class);

    public static void main(String[] args) {
        AbitResources.initializeResources(args[0]);
        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());

        int threads = AbitResources.instance.getInt("number.of.threads", 4);

        logger.info("Reading SILO calib5 population with real LOS");
        DataSet dataSet = new MarylandLosDataReader().readData();

        double toll = AbitResources.instance.getDouble("auto.toll", 0.0);
        abm.models.maryland.MarylandFullModeChoice.setToll(toll);
        logger.info("Auto toll = $" + toll);

        logger.info("Creating Maryland RTS models");
        ModelSetup modelSetup = new ModelSetupMaryland(dataSet);

        logger.info("Generating plans using " + threads + " threads");
        ConcurrentExecutor executor = ConcurrentExecutor.fixedPoolService(threads);
        Map<Integer, List<Person>> byThread = new HashMap<>();
        int i = 0;
        for (Household hh : dataSet.getHouseholds().values()) {
            for (Person p : hh.getPersons()) {
                byThread.computeIfAbsent(i % threads, k -> new ArrayList<>()).add(p);
                i++;
            }
        }
        for (int t = 0; t < threads; t++) {
            executor.addTaskToQueue(new PlanGenerator(dataSet, modelSetup, t)
                    .setPersons(byThread.getOrDefault(t, new ArrayList<>())));
        }
        executor.execute();

        // iterative ASC calibration against the real generated tours (base, no-toll only)
        if (toll == 0.0 && modelSetup.getTourModeChoice() instanceof abm.models.maryland.MarylandFullModeChoice) {
            abm.models.maryland.MarylandFullModeChoice mc = (abm.models.maryland.MarylandFullModeChoice) modelSetup.getTourModeChoice();
            mc.reapplyAndCalibrate(dataSet, 40);
            mc.writeReanchored();   // persist the refined re-anchored coefficients
        } else if (modelSetup.getTourModeChoice() instanceof abm.models.maryland.MarylandFullModeChoice) {
            // toll scenario: keep base ASCs, just re-apply mode choice with the toll in effect
            ((abm.models.maryland.MarylandFullModeChoice) modelSetup.getTourModeChoice()).applyToAllTours(dataSet);
        }

        logger.info("Applying RTS ordered-logit stop-frequency model");
        new abm.models.maryland.MarylandStopModel(dataSet).run();

        String sfx = AbitResources.instance.getString("output.suffix");
        if (sfx == null) sfx = "";
        String out = AbitResources.instance.getString("base.directory") + "/output/";
        new File(out).mkdirs();
        logger.info("Printing plans to " + out + " (suffix '" + sfx + "')");
        try { new ActivityPrinter(dataSet).print(out + "/activities" + sfx + ".csv"); }
        catch (Exception e) { logger.error("ActivityPrinter failed", e); }
        try { new LegPrinter(dataSet).print(out + "/legs" + sfx + ".csv"); }
        catch (Exception e) { logger.error("LegPrinter failed", e); }
        logger.info("DONE. persons=" + dataSet.getPersons().size());
    }
}
