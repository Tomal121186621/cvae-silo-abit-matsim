package abm.models.destinationChoice;

import abm.data.geo.Location;
import abm.data.plans.Activity;
import abm.data.plans.Tour;
import abm.data.pop.Person;

public interface DestinationChoice {

    /**
     * Selects the destination of a main activity (based on home)
     * @param person
     * @param activity
     * @return
     */
    void selectMainActivityDestination(Person person, Activity activity);

    /**
     * Selects the destination of a stop based on home and on the location of
     * the previous and the following activity
     * @param person
     * @param tour
//     * @param previousActivity
     * @param activity
//     * @param followingActivity
     * @return
     */
//    void selectStopDestination(Person person, Activity previousActivity,
//                                   Activity activity, Activity followingActivity);

    void selectStopDestination(Person person, Tour tour
                               ,Activity activity);


}
