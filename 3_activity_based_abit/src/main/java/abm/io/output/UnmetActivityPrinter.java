package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Person;

import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class UnmetActivityPrinter {

    private final DataSet dataSet;

    public UnmetActivityPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println(Activity.getHeader());

        for (Person person : dataSet.getPersons().values()) {
            if (person.getHousehold().getSimulated()) {
                if (person.getPlan() != null) {
                    for (Activity activity : person.getPlan().getUnmetActivities().values()) {
                        pw.println(activity.toString());
                    }
                }
            } else {
            }
        }
        pw.close();
    }
}
