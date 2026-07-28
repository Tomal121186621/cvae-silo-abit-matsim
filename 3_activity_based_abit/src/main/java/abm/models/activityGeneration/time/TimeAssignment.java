package abm.models.activityGeneration.time;

import abm.data.plans.Activity;

public interface TimeAssignment {

    void assignStartTimeAndDuration(Activity activity);

    void assignDurationToStop(Activity activity);

    void assignDurationAndThenStartTime(Activity activity);
}
