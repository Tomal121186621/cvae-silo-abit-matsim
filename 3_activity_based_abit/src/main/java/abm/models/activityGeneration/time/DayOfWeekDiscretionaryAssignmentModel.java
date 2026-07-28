package abm.models.activityGeneration.time;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.timeOfDay.BlockedTimeOfWeekLinkedList;
import de.tum.bgu.msm.util.MitoUtil;

import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class DayOfWeekDiscretionaryAssignmentModel implements DayOfWeekDiscretionaryAssignment {

    private final DataSet dataSet;
    private final Map<DayOfWeek, Double> dayProbabilities;

    public DayOfWeekDiscretionaryAssignmentModel(DataSet dataSet) {
        this.dataSet = dataSet;
        dayProbabilities = new HashMap<>();
    }

    @Override
    public void assignDayOfWeek(Activity activity) {

        Map<DayOfWeek, Double> dayProbabilities = new HashMap<>();

        for (DayOfWeek dayOfWeek : DayOfWeek.values()) {

            BlockedTimeOfWeekLinkedList blockedTime = activity.getPerson().getPlan().getBlockedTimeOfDay();

            double availableTimeSlots = (double) 60 / 15 * 24 - blockedTime.getForThisDayOfWeek(dayOfWeek).getInternalList().size();

            if (activity.getPurpose().equals(Purpose.SHOPPING) && dayOfWeek.equals(DayOfWeek.SUNDAY)) {
                availableTimeSlots = 0.0;
            }

            dayProbabilities.put(dayOfWeek, (double) availableTimeSlots);
        }
        DayOfWeek select = MitoUtil.select(dayProbabilities);
        activity.setDayOfWeek(select);
    }
}
