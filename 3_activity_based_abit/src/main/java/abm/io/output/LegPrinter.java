package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Leg;
import abm.data.plans.Tour;
import abm.data.pop.Person;

import java.io.FileNotFoundException;
import java.io.PrintWriter;

public class LegPrinter {

    private final DataSet dataSet;

    public LegPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println(Leg.getHeader());


        for (Person person : dataSet.getPersons().values()) {
            if (person.getPlan() != null){
                for (Tour tour : person.getPlan().getTours().values()) {
                    for (Leg leg : tour.getLegs().values()) {
                        pw.println(leg.toString());
                    }

                }
            }
        }

        pw.close();


    }
}
