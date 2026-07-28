package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.utils.AbitUtils;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

public class PersonSummaryPrinter {

    private final DataSet dataSet;

    public PersonSummaryPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println("Person, Age, Occupation, Gender, HabitualMode, Bike, DrivingLicense");

        for (Household household:dataSet.getHouseholds().values()){

            if (household.getSimulated()){


                for (Person person:household.getPersons()){

                    pw.println(person.getId() + "," + person.getAge() + "," + person.getOccupation().toString() + ","
                            + person.getGender().toString() + "," + person.getHabitualMode().toString() + ","
                            + person.hasBicycle() + "," + person.isHasLicense());

                }
            }
        }

//        pw.println(Activity.getHeader());
//
//
//        for (Person person : dataSet.getPersons().values()) {
//            if (person.getPlan() != null) {
//
//                Map<Purpose, Double> durations = new HashMap<>();
//                Map<Purpose, Integer> activities = new HashMap<>();
//                int mandatoryTours = 0;
//                int discretionaryTours = 0;
//
//
//                for (Tour tour : person.getPlan().getTours().values()) {
//                    if (Purpose.getMandatoryPurposes().contains(tour.getMainActivity().getPurpose())) {
//                        mandatoryTours++;
//                    } else {
//                        discretionaryTours++;
//                    }
//                    for (Activity activity : tour.getActivities().values()) {
//                        activities.putIfAbsent(activity.getPurpose(), 0);
//                        durations.putIfAbsent(activity.getPurpose(), 0.);
//                        activities.put(activity.getPurpose(), activities.get(activity.getPurpose()) + 1);
//                        durations.put(activity.getPurpose(), durations.get(activity.getPurpose()) + activity.getDuration());
//
//                    }
//
//                }
//
//
//                for (Purpose p : Purpose.getAllPurposes()){
//                    StringBuilder builder = new StringBuilder();
//                    builder.append(person.getId()).append(AbitUtils.SEPARATOR);
//                    builder.append(mandatoryTours).append(AbitUtils.SEPARATOR);
//                    builder.append(discretionaryTours).append(AbitUtils.SEPARATOR);
//                    builder.append(activities.get(p)).append(AbitUtils.SEPARATOR);
//                    builder.append(durations.get(p));
//                    pw.println(builder);
//                }
//
//
//
//            }
//        }

        pw.close();


    }
}
