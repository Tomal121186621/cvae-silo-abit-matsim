package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.pop.Household;
import abm.data.pop.Person;
import de.tum.bgu.msm.data.person.Occupation;

import java.io.FileNotFoundException;
import java.io.PrintWriter;

public class PersonHabitualModeGcPrinter {

    private final DataSet dataSet;

    public PersonHabitualModeGcPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println("Person, Occupation, Age, DistanceToMand, HabitualMode, GcCarD, GcCarP, GcPt, GcBike, GcWalk ");

        for (Household household:dataSet.getHouseholds().values()){

            if (household.getSimulated()){

                for (Person person:household.getPersons()){

                    if(person.getOccupation().equals(Occupation.EMPLOYED)||person.getOccupation().equals(Occupation.STUDENT)){

                        double travelDistanceAuto = 0;
                        if (person.getOccupation().equals(Occupation.EMPLOYED)){
                            travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getJob().getLocation(), Mode.UNKNOWN, person.getJob().getStartTime_min());
                        } else {
                            travelDistanceAuto = dataSet.getTravelDistances().getTravelDistanceInMeters(person.getHousehold().getLocation(), person.getSchool().getLocation(), Mode.UNKNOWN, person.getSchool().getStartTime_min());
                        }

                        pw.println(person.getId() + "," + person.getOccupation().toString() + "," + person.getAge() + "," + travelDistanceAuto + "," + person.getHabitualMode().toString() + ","
                                + person.getHabitualModeGcCarD() + "," + person.getHabitualModeGcCarP() + ","
                                + person.getHabitualModeGcPT() + "," + person.getHabitualModeGcBike() + "," + person.getHabitualModeGcWalk());
                    }



                }
            }
        }

        pw.close();


    }

}
