package abm.models.activityGeneration.splitByType;

import abm.data.plans.Activity;
import abm.data.plans.Leg;
import abm.data.plans.StopType;
import abm.data.plans.Tour;
import abm.data.pop.Person;
import abm.data.timeOfDay.BlockedTimeOfWeekLinkedList;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;

import java.time.DayOfWeek;

public class SimpleSplitStopTypeModelWithAvailability implements SplitStopType {

    private int counterErrors = 0;

    @Override
    public StopType getStopType(Person person, Activity activity, Tour tour) {

        BlockedTimeOfWeekLinkedList availableTimeOfDay = person.getPlan().getBlockedTimeOfDay();

        final DayOfWeek dayOfWeek = tour.getMainActivity().getDayOfWeek();
        int midnight = dayOfWeek.ordinal() * 24 * 60;

        availableTimeOfDay = availableTimeOfDay.getForThisDayOfWeek(dayOfWeek);

        int tourStart_min = tour.getLegs().firstKey();
        Leg lastLeg = tour.getLegs().get(tour.getLegs().lastKey());
        int tourEnd_min = tour.getLegs().lastKey() + lastLeg.getTravelTime_min();


        //count periods before
        int nBefore = 0;
        for (int t = tourStart_min - InternalProperties.SEARCH_INTERVAL_MIN; t > midnight; t -= InternalProperties.SEARCH_INTERVAL_MIN) {
            if (availableTimeOfDay.isAvailable(t) == 1) {
                nBefore++;
            } else {
                //until it finds the previous blocked time
                break;
            }
        }

        //count periods after
        int nAfter = 0;
        for (int t = tourEnd_min + InternalProperties.SEARCH_INTERVAL_MIN; t < midnight + 60 * 24; t += InternalProperties.SEARCH_INTERVAL_MIN) {
            if (availableTimeOfDay.isAvailable(t) == 1) {
                nAfter++;
            } else {
                //until it finds the next blocked time
                break;
            }
        }


        if (nAfter * 15 > activity.getDuration() && nBefore * 15 > activity.getDuration()) {
            double probabilityBefore = Double.valueOf(nBefore) / (nBefore + nAfter);
            if (AbitUtils.randomObject.nextDouble() < probabilityBefore) {
                return StopType.BEFORE;
            } else {
                return StopType.AFTER;
            }

        } else if (nAfter * 15 > activity.getDuration()) {
            return StopType.AFTER;
        } else if (nBefore * 15 > activity.getDuration()) {
            return StopType.BEFORE;
        } else {
            counterErrors++;
            //System.out.println("Cannot allocate this stop: n = " + counterErrors);
            return null;
        }


    }

}
