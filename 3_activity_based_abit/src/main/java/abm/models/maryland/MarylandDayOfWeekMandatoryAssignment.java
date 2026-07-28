package abm.models.maryland;

import abm.data.plans.Purpose;
import abm.data.pop.Person;
import abm.models.activityGeneration.time.DayOfWeekMandatoryAssignment;
import de.tum.bgu.msm.util.MitoUtil;

import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

/**
 * Maryland mandatory (WORK) day-of-week assignment: concentrates workdays on the five WEEKDAYS.
 *
 * {@link MarylandFrequencyGenerator} returns 5 workdays for an EMPLOYED person, so this model
 * selects (without replacement) 5 distinct days from a weekday-heavy distribution: Mon-Fri carry
 * essentially all the weight (weekend weights are near zero, only reached in the rare event a
 * weekday is exhausted first). The result is a work tour on essentially every weekday, so the
 * representative-weekday extraction downstream always carries the commute.
 */
public class MarylandDayOfWeekMandatoryAssignment implements DayOfWeekMandatoryAssignment {

    @Override
    public DayOfWeek[] assignDaysOfWeek(int numberOfDaysOfWeek, Purpose purpose, Person person) {
        Map<DayOfWeek, Double> dayProbabilities = new HashMap<>();
        dayProbabilities.put(DayOfWeek.MONDAY, 1.0);
        dayProbabilities.put(DayOfWeek.TUESDAY, 1.0);
        dayProbabilities.put(DayOfWeek.WEDNESDAY, 1.0);
        dayProbabilities.put(DayOfWeek.THURSDAY, 1.0);
        dayProbabilities.put(DayOfWeek.FRIDAY, 1.0);
        dayProbabilities.put(DayOfWeek.SATURDAY, 0.10);
        dayProbabilities.put(DayOfWeek.SUNDAY, 0.03);

        DayOfWeek[] daysOfWeek = new DayOfWeek[numberOfDaysOfWeek];
        for (int i = 0; i < numberOfDaysOfWeek; i++) {
            final DayOfWeek select = MitoUtil.select(dayProbabilities);
            daysOfWeek[i] = select;
            dayProbabilities.remove(select);
        }
        return daysOfWeek;
    }
}
