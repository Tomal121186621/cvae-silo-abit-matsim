package abm.models.modeChoice;

import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;

public interface TourModeChoice {

    void chooseMode(Person person, Tour tour);

    void chooseMode(Person person, Tour tour, Purpose purpose);

    Mode chooseMode(Person person, Tour tour, Purpose purpose, Boolean carAvailable);

    void checkCarAvailabilityAndChooseMode(Household household, Person person, Tour tour, Purpose purpose);

}
