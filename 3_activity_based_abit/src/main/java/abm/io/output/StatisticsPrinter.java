package abm.io.output;

import abm.RunAbit;
import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Person;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

public class StatisticsPrinter {

    private final DataSet dataSet;
    static Logger logger = Logger.getLogger(StatisticsPrinter.class);

    public StatisticsPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        String header = "Distance";
        for (Purpose purpose : Purpose.values()) {
            header = header.concat("," + purpose.toString());
        }
        header = header.concat("," + "workSP");
        header = header.concat("," + "eduSP");
        pw.println(header);

        Map<Integer, Map<Purpose, Integer>> distanceByPurpose = new HashMap<>();
        Map<Integer, Map<String, Integer>> distanceByPurposeSP = new HashMap<>();
        Map<Purpose, Double> totaldistanceByPurpose = new HashMap<>();
        Map<String, Double> totaldistanceByPurposeSP = new HashMap<>();
        Map<Purpose, Double> totalTripsByPurpose = new HashMap<>();
        int counterWorkers = 0;
        int counterStudents = 0;
        int counterInactivePersons = 0;
        for (Person person: dataSet.getPersons().values()) {
            if (person.getPlan() != null) {
                for (Tour tour : person.getPlan().getTours().values()) {
                    if (tour.getMainActivity() != null && tour.getMainActivity().getLocation() != null) {
                        abm.data.plans.Purpose purpose = tour.getMainActivity().getPurpose();
                        abm.data.geo.Location location = tour.getMainActivity().getLocation();
                        double rawDistance = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), location, Mode.UNKNOWN, 0.);
                        int refinedDistance = (int) Math.round(rawDistance);
                        if (purpose.equals(Purpose.WORK) && person.getOccupation().equals(Occupation.EMPLOYED)) {
                            updateMap(distanceByPurposeSP, refinedDistance, "workSP");
                            updateMap(totaldistanceByPurposeSP, rawDistance, "workSP");
                            counterWorkers++;
                        } else if (purpose.equals(Purpose.EDUCATION) && person.getOccupation().equals(Occupation.STUDENT)) {
                            updateMap(distanceByPurposeSP, refinedDistance, "eduSP");
                            updateMap(totaldistanceByPurposeSP, rawDistance, "eduSP");
                            counterStudents++;
                        } else {
                            updateMap(distanceByPurpose, refinedDistance, purpose);
                            updateMap(totaldistanceByPurpose, rawDistance, purpose);
                            updateMap(totalTripsByPurpose, 1., purpose);
                        }
                    }
                }
            } else {
                counterInactivePersons++;
            }
        }

        for (int i : distanceByPurpose.keySet()) {
            String txt = String.valueOf(i);
            if (distanceByPurpose.containsKey(i)) {
                for (Purpose purpose : Purpose.values()) {
                    if (distanceByPurpose.get(i).containsKey(purpose)) {
                        Integer trips = distanceByPurpose.get(i).get(purpose);
                        txt = txt.concat("," + trips);
                    } else {
                        txt = txt.concat("," + 0);
                    }
                }
            } else {
                for (Purpose purpose : Purpose.values()) {
                    txt = txt.concat("," + 0);
                }
            }
            if (distanceByPurposeSP.containsKey(i)) {
                if (distanceByPurposeSP.get(i).containsKey("workSP")) {
                    txt = txt.concat("," + distanceByPurposeSP.get(i).get("workSP"));
                } else {
                    txt = txt.concat("," + 0);
                }
                if (distanceByPurposeSP.get(i).containsKey("eduSP")) {
                    txt = txt.concat("," + distanceByPurposeSP.get(i).get("eduSP"));
                } else {
                    txt = txt.concat("," + 0);
                }
            } else {
                txt = txt.concat("," + 0);
                txt = txt.concat("," + 0);
            }
            pw.println(txt);
        }
        pw.close();

        for (Purpose purpose : Purpose.values()){
            double avgDistance = 0;
            if (totalTripsByPurpose.containsKey(purpose)) {
                avgDistance =totaldistanceByPurpose.get(purpose) / totalTripsByPurpose.get(purpose) / 1000;
            }
            logger.info("Average distance for " + purpose.toString() + " activities: " + avgDistance);
        }
        double avgDistanceWorkSP = totaldistanceByPurposeSP.get("workSP") / counterWorkers / 1000;
        double avgDistanceEduSP = totaldistanceByPurposeSP.get("eduSP") / counterStudents / 1000;
        logger.info("Average distance for work activities in SP: " + avgDistanceWorkSP + " for " + counterWorkers + " workers.");
        logger.info("Average distance for education activities in SP: " + avgDistanceEduSP + " for " + counterStudents + " students.");
        logger.info("Number of inactive persons: " + counterInactivePersons);
    }


    private static void updateMap(Map<Integer, Map<Purpose, Integer>> map, Integer key, Purpose purpose) {
        if (map.containsKey(key)) {
            if (map.get(key).containsKey(purpose)) {
                int existingCount = map.get(key).get(purpose);
                map.get(key).replace(purpose, existingCount + 1);
            } else {
                map.get(key).put(purpose, 1);
            }
        } else {
            Map<Purpose, Integer> subMap = new HashMap<>();
            subMap.put(purpose, 1);
            map.put(key, subMap);
        }
    }

    private static void updateMap(Map<Integer, Map<String, Integer>> map, Integer key, String purpose) {
        if (map.containsKey(key)) {
            if (map.get(key).containsKey(purpose)) {
                int existingCount = map.get(key).get(purpose);
                map.get(key).replace(purpose, existingCount + 1);
            } else {
                map.get(key).put(purpose, 1);
            }
        } else {
            Map<String, Integer> subMap = new HashMap<>();
            subMap.put(purpose, 1);
            map.put(key, subMap);
        }
    }

    private static void updateMap(Map<Purpose, Double> map, Double rawDistance,Purpose purpose) {

        if (map.containsKey(purpose)) {
            double existingCount = map.get(purpose);
            map.replace(purpose, existingCount + rawDistance);
        } else {
            map.put(purpose, rawDistance);
        }

    }

    private static void updateMap(Map<String, Double> map, Double rawDistance,String purpose) {

        if (map.containsKey(purpose)) {
            double existingCount = map.get(purpose);
            map.replace(purpose, existingCount + rawDistance);
        } else {
            map.put(purpose, rawDistance);
        }

    }

}
