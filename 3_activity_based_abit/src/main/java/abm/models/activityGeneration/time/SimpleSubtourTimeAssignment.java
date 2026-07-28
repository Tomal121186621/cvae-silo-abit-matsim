package abm.models.activityGeneration.time;

import abm.data.plans.Activity;

public class SimpleSubtourTimeAssignment implements SubtourTimeAssignment {
    @Override
    public void assignTimeToSubtourActivity(Activity subtourActivity, Activity mainActivity) {

        subtourActivity.setDayOfWeek(mainActivity.getDayOfWeek());
        subtourActivity.setStartTime_min((mainActivity.getStartTime_min() + mainActivity.getEndTime_min())/2);
        subtourActivity.setEndTime_min(subtourActivity.getStartTime_min() + 5);

    }
}
