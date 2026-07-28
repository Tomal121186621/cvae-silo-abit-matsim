package abm.models.activityGeneration.splitByType;

import abm.data.plans.Activity;
import abm.data.plans.StopType;
import abm.data.plans.Tour;
import abm.data.pop.Person;

public interface SplitStopType {
    StopType getStopType(Person person, Activity activity, Tour tour);
}
