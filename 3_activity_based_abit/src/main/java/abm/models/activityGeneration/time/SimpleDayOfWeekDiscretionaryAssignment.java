package abm.models.activityGeneration.time;

import abm.utils.AbitUtils;
import abm.data.plans.Activity;

import java.time.DayOfWeek;

public class SimpleDayOfWeekDiscretionaryAssignment implements DayOfWeekDiscretionaryAssignment {

    @Override
    public void assignDayOfWeek(Activity activity) {
        activity.setDayOfWeek(DayOfWeek.of(AbitUtils.getRandomObject().nextInt(7) + 1));
    }
}
