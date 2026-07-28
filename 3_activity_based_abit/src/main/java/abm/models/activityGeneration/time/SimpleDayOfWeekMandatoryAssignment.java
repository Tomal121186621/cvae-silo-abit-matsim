package abm.models.activityGeneration.time;

import abm.data.plans.Purpose;
import abm.data.pop.Person;
import de.tum.bgu.msm.util.MitoUtil;

import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SimpleDayOfWeekMandatoryAssignment implements DayOfWeekMandatoryAssignment {


    @Override
    public DayOfWeek[] assignDaysOfWeek(int numberOfDaysOfWeek, Purpose purpose, Person person) {

        Map<DayOfWeek, Double> dayProbabilities = new HashMap<>();

        dayProbabilities.put(DayOfWeek.MONDAY, 1.);
        dayProbabilities.put(DayOfWeek.TUESDAY, 1.);
        dayProbabilities.put(DayOfWeek.WEDNESDAY, 1.0);
        dayProbabilities.put(DayOfWeek.THURSDAY, 1.0);
        dayProbabilities.put(DayOfWeek.FRIDAY, 0.7);
        dayProbabilities.put(DayOfWeek.SATURDAY, 0.15);
        dayProbabilities.put(DayOfWeek.SUNDAY, 0.05);

        DayOfWeek[] daysOfWeek = new DayOfWeek[numberOfDaysOfWeek];

        for (int i = 0; i < numberOfDaysOfWeek; i++) {
            final DayOfWeek select = MitoUtil.select(dayProbabilities);
            daysOfWeek[i] = select;
            dayProbabilities.remove(select);
        }
        return daysOfWeek;
    }
}
