package abm.models.activityGeneration.time;

import abm.utils.AbitUtils;
import abm.data.plans.Activity;

public class SimpleTimeAssignment implements TimeAssignment {



    //TODO Split into assignStartTime and assignDuration (Stops do not need start time, since it is derived from the main tour)
    @Override
    public void assignStartTimeAndDuration(Activity activity) {

        int midnight = (activity.getDayOfWeek().getValue() - 1) * 24 * 3600/60;
        int startTime = (int) Math.max(0, 10 * 3600 + AbitUtils.getRandomObject().nextGaussian() * 2 * 3600)/60;
        int duration = (int) Math.max(60, 1 * 3600 + AbitUtils.getRandomObject().nextGaussian() * 4 * 3600)/60;

        //Todo add a method for scheduling
        activity.setStartTime_min(midnight + startTime);
        activity.setEndTime_min(midnight +  startTime + duration);

    }

    public void assignDurationToStop(Activity activity) {

        int midnight = (activity.getDayOfWeek().getValue() - 1) * 24 * 3600/60;
        int startTime = 0/60;
        int duration = (int) Math.max(60, 1 * 3600 + AbitUtils.getRandomObject().nextGaussian() * 4 * 3600)/60;

        //Todo add a method for scheduling
        activity.setStartTime_min(midnight + startTime);
        activity.setEndTime_min(midnight + startTime + duration);

    }

    @Override
    public void assignDurationAndThenStartTime(Activity activity) {

    }
}
