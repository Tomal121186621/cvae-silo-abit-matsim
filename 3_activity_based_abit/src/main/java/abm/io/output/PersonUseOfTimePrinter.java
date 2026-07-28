package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Plan;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Person;
import abm.utils.AbitUtils;
import abm.utils.PlanTools;
import org.apache.log4j.Logger;


import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

public class PersonUseOfTimePrinter {

    private final static Logger logger = Logger.getLogger(PersonUseOfTimePrinter.class);
    private final DataSet dataSet;
    private static int INTERVAL_MIN = 30;
    private final Map<Purpose, Map<Integer, Integer>> timeUseByPurpose = new HashMap<>();

    public PersonUseOfTimePrinter(DataSet dataSet) {
        this.dataSet = dataSet;
        for (Purpose p : Purpose.getAllPurposes()) {
            timeUseByPurpose.putIfAbsent(p, new HashMap<>());
            for (int j = PlanTools.startOfTheWeek(); j <= PlanTools.endOfTheWeek(); j = j + INTERVAL_MIN) {
                timeUseByPurpose.get(p).put(j, 0);
            }

        }
    }

    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println("purpose,interval,count");

        int errors = 0;
        for (Person person : dataSet.getPersons().values()) {
            if (person.getPlan() != null) {
                for (Tour tour : person.getPlan().getTours().values()) {
                    for (Activity activity : tour.getActivities().values()) {

                        int intervalStart = (int) Math.floor(activity.getStartTime_min() / INTERVAL_MIN);
                        int intervaEnd = (int) Math.ceil(activity.getEndTime_min() / INTERVAL_MIN);

                        if (intervaEnd * INTERVAL_MIN > PlanTools.startOfTheWeek() && intervalStart * INTERVAL_MIN > PlanTools.startOfTheWeek() &&
                                intervaEnd * INTERVAL_MIN < PlanTools.endOfTheWeek() && intervalStart * INTERVAL_MIN < PlanTools.endOfTheWeek()) {

                            for (int i = intervalStart; i <= intervaEnd; i++) {
                                int newCount = timeUseByPurpose.get(activity.getPurpose()).get(i * INTERVAL_MIN) + 1;
                                timeUseByPurpose.get(activity.getPurpose()).put(i * INTERVAL_MIN, newCount);
                            }

                        } else {
                            errors++;
                        }


                    }


                }
            }
        }
        logger.info("Errors: " + errors + " times outside of the week times");

        for (Purpose p : Purpose.getAllPurposes()) {
            timeUseByPurpose.putIfAbsent(p, new HashMap<>());
            for (int j = PlanTools.startOfTheWeek(); j <= PlanTools.endOfTheWeek(); j = j + INTERVAL_MIN) {
                pw.println(p + AbitUtils.SEPARATOR + j + AbitUtils.SEPARATOR + timeUseByPurpose.get(p).get(j));
            }

        }

        pw.close();
    }
}
