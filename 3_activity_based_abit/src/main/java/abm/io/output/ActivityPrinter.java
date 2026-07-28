package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Leg;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Person;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class ActivityPrinter {

    private final DataSet dataSet;

    public ActivityPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println(Activity.getHeader());


        for (Person person : dataSet.getPersons().values()) {

            if (person.getHousehold().getSimulated()) {

                if (person.getPlan() != null) {

                    if (person.getPlan().getTours().size() == 0) {

                        for (DayOfWeek day : DayOfWeek.values()) {

                            Activity homeAct = new Activity(person, Purpose.HOME);
                            homeAct.setStartTime_min(day.ordinal() * 60 * 24);
                            homeAct.setEndTime_min((day.ordinal() + 1) * 60 * 24 - 1);
                            homeAct.setLocation(person.getHousehold().getLocation());
                            homeAct.setDayOfWeek(day);

                            pw.println(homeAct);
                        }


                    } else {
                        Map<DayOfWeek, Boolean> dayHasTour = new HashMap<>();
                        for (Tour tour : person.getPlan().getTours().values()) {


                            for (Leg leg : tour.getLegs().values()) {
                                pw.println(leg.getPreviousActivity().toString());
                                if (tour.getLegs().get(tour.getLegs().lastKey()).equals(leg)){
                                    pw.println(leg.getNextActivity().toString());
                                }

                            }


//                            for (Activity activity : tour.getActivities().values()) {
//                                pw.println(activity.toString());
//                            }

                        }
                    }


                }
            } else {

            }


        }

        pw.close();


    }

}
