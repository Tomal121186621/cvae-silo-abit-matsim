package abm.io.output;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Tour;
import abm.data.pop.Person;

import java.io.FileNotFoundException;
import java.io.PrintWriter;

public class TourPrinter {

    private final DataSet dataSet;

    public TourPrinter(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    public void print(String fileName) throws FileNotFoundException {

        PrintWriter pw = new PrintWriter(fileName);

        pw.println(Tour.getHeader());


        for (Person person : dataSet.getPersons().values()) {
            if (person.getPlan() != null){
                for (Tour tour : person.getPlan().getTours().values()) {
                        pw.println(tour.toString());
                }
            }
        }

        pw.close();


    }

}
