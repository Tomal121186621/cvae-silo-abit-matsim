package abm.models.activityGeneration.time;

import abm.data.plans.Activity;

public interface SubtourTimeAssignment {

    void assignTimeToSubtourActivity(Activity subtourActivity, Activity mainActivity);

}
