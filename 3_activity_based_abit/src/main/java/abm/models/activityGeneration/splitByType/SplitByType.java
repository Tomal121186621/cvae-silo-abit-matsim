package abm.models.activityGeneration.splitByType;

import abm.data.plans.Activity;
import abm.data.plans.DiscretionaryActivityType;
import abm.data.pop.Person;

public interface SplitByType {

    /**
     * Assigns an activity type to a discretionary activity
     * @param activity
     * @param person
     * @return
     */


    DiscretionaryActivityType assignActType(Activity activity, Person person);

    DiscretionaryActivityType assignActTypeForDiscretionaryTourActs(Activity activity, Person person, int numActsNotOnMandatoryTours);
}
